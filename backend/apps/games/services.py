import hashlib
import hmac
import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F, Value
from django.db.models.functions import Greatest
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.statistics.models import PlayerStats

from .events import record_game_event
from .models import Game, GameParticipant, GameResult

INVITE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class GameConflict(APIException):
    status_code = 409
    default_detail = "La partie ne peut pas effectuer cette action dans son état actuel."
    default_code = "game_conflict"


def _generate_invite_code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(10))


def _invite_digest(code: str) -> str:
    normalized = "".join(code.upper().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _lock_game(game_id):
    try:
        return Game.objects.select_for_update().get(pk=game_id)
    except Game.DoesNotExist as exc:
        raise NotFound("Partie introuvable.") from exc


def _participant(game: Game, user: User) -> GameParticipant:
    try:
        return GameParticipant.objects.get(game=game, user=user)
    except GameParticipant.DoesNotExist as exc:
        raise PermissionDenied("Vous ne participez pas à cette partie.") from exc


def _require_waiting(game: Game) -> None:
    if game.status != Game.Status.WAITING:
        raise GameConflict("Cette partie n’accepte plus de modification de salon.")


def create_game(*, host: User, mode: str, visibility: str, max_players: int, invite_expires_in_hours: int):
    if mode == Game.Mode.SOLO:
        visibility = Game.Visibility.PRIVATE

    invite_code = _generate_invite_code() if visibility == Game.Visibility.PRIVATE and mode == Game.Mode.MULTIPLAYER else None
    invite_hash = _invite_digest(invite_code) if invite_code else None
    expires_at = (
        timezone.now() + timedelta(hours=invite_expires_in_hours)
        if invite_code
        else None
    )

    with transaction.atomic():
        game = Game.objects.create(
            host=host,
            mode=mode,
            visibility=visibility,
            max_players=max_players,
            invite_code_hash=invite_hash,
            invite_expires_at=expires_at,
        )
        GameParticipant.objects.create(
            game=game,
            user=host,
            kind=GameParticipant.Kind.HUMAN,
            seat_number=1,
            display_name=host.display_name,
            is_ready=(mode == Game.Mode.SOLO),
        )
        if mode == Game.Mode.SOLO:
            for seat_number in range(2, max_players + 1):
                GameParticipant.objects.create(
                    game=game,
                    kind=GameParticipant.Kind.BOT,
                    seat_number=seat_number,
                    display_name=f"Bot {seat_number - 1}",
                    bot_difficulty="normal",
                    is_ready=True,
                )
        record_game_event(
            game,
            "game.created",
            actor=host,
            public_payload={
                "mode": mode,
                "visibility": visibility,
                "max_players": max_players,
            },
        )
    return game, invite_code


def list_available_games():
    return (
        Game.objects.filter(
            mode=Game.Mode.MULTIPLAYER,
            visibility=Game.Visibility.PUBLIC,
            status=Game.Status.WAITING,
        )
        .annotate(occupied_seats=Count("participants"))
        .filter(occupied_seats__lt=F("max_players"))
        .select_related("host")
        .prefetch_related("participants")
        .order_by("-created_at")
    )


def list_my_games(user: User):
    return (
        Game.objects.filter(participants__user=user)
        .select_related("host", "result__winner")
        .prefetch_related("participants")
        .distinct()
    )


def get_game_for_user(*, game_id, user: User) -> Game:
    try:
        game = (
            Game.objects.select_related("host", "result__winner")
            .prefetch_related("participants")
            .get(pk=game_id)
        )
    except Game.DoesNotExist as exc:
        raise NotFound("Partie introuvable.") from exc
    if game.visibility == Game.Visibility.PRIVATE:
        _participant(game, user)
    elif game.status != Game.Status.WAITING:
        _participant(game, user)
    return game


def join_game(*, game_id, user: User, invite_code: str | None = None) -> Game:
    with transaction.atomic():
        game = _lock_game(game_id)
        _require_waiting(game)
        if game.mode != Game.Mode.MULTIPLAYER:
            raise GameConflict("Une partie solo ne peut pas être rejointe.")
        if game.visibility == Game.Visibility.PRIVATE:
            if not invite_code:
                raise PermissionDenied("Un code d’invitation est requis.")
            if (
                game.invite_expires_at
                and game.invite_expires_at <= timezone.now()
            ):
                raise GameConflict("Le code d’invitation a expiré.")
            supplied_hash = _invite_digest(invite_code)
            if not game.invite_code_hash or not hmac.compare_digest(
                supplied_hash, game.invite_code_hash
            ):
                raise PermissionDenied("Code d’invitation invalide.")

        if GameParticipant.objects.filter(game=game, user=user).exists():
            raise GameConflict("Vous participez déjà à cette partie.")
        participants = list(
            GameParticipant.objects.filter(game=game).order_by("seat_number")
        )
        if len(participants) >= game.max_players:
            raise GameConflict("Cette partie est complète.")

        occupied = {participant.seat_number for participant in participants}
        seat_number = next(
            seat for seat in range(1, game.max_players + 1) if seat not in occupied
        )
        participant = GameParticipant.objects.create(
            game=game,
            user=user,
            kind=GameParticipant.Kind.HUMAN,
            seat_number=seat_number,
            display_name=user.display_name,
        )
        record_game_event(
            game,
            "player.joined",
            actor=user,
            public_payload={
                "participant_id": str(participant.pk),
                "seat_number": seat_number,
                "display_name": participant.display_name,
            },
        )
    return game


def leave_game(*, game_id, user: User) -> Game:
    with transaction.atomic():
        game = _lock_game(game_id)
        _require_waiting(game)
        participant = _participant(game, user)
        record_game_event(
            game,
            "player.left",
            actor=user,
            public_payload={
                "participant_id": str(participant.pk),
                "seat_number": participant.seat_number,
                "display_name": participant.display_name,
            },
        )
        participant.delete()

        remaining_humans = list(
            GameParticipant.objects.filter(
                game=game, kind=GameParticipant.Kind.HUMAN
            ).order_by("seat_number", "joined_at")
        )
        if not remaining_humans:
            game.status = Game.Status.CANCELLED
            game.save(update_fields=["status", "updated_at"])
            record_game_event(game, "game.cancelled", actor=None)
        elif game.host_id == user.pk:
            game.host = remaining_humans[0].user
            game.save(update_fields=["host", "updated_at"])
            record_game_event(
                game,
                "host.changed",
                actor=game.host,
                public_payload={
                    "host_display_name": game.host.display_name,
                },
            )
        return game


def set_ready(*, game_id, user: User, is_ready: bool) -> Game:
    with transaction.atomic():
        game = _lock_game(game_id)
        _require_waiting(game)
        participant = _participant(game, user)
        if participant.is_ready == is_ready:
            return game
        participant.is_ready = is_ready
        participant.save(update_fields=["is_ready"])
        record_game_event(
            game,
            "player.ready_changed",
            actor=user,
            public_payload={
                "participant_id": str(participant.pk),
                "is_ready": is_ready,
            },
        )
    return game


def start_game(*, game_id, user: User) -> Game:
    with transaction.atomic():
        game = _lock_game(game_id)
        _require_waiting(game)
        if game.host_id != user.pk:
            raise PermissionDenied("Seul l’hôte peut démarrer la partie.")
        participants = list(
            GameParticipant.objects.filter(game=game).order_by("seat_number")
        )
        humans = [p for p in participants if p.kind == GameParticipant.Kind.HUMAN]
        if game.mode == Game.Mode.MULTIPLAYER and len(humans) < 2:
            raise ValidationError("Il faut au moins deux joueurs humains.")
        if any(not participant.is_ready for participant in humans):
            raise GameConflict("Tous les joueurs humains doivent être prêts.")
        if len(participants) < 2:
            raise ValidationError("Il faut au moins deux participants.")
        game.status = Game.Status.ACTIVE
        game.started_at = timezone.now()
        game.save(update_fields=["status", "started_at", "updated_at"])
        record_game_event(game, "game.started", actor=user)
    return game


def finish_game(
    *,
    game_id,
    winner_participant_id,
    kilometers_by_participant: dict,
):
    """Finalise une partie depuis une future intégration de moteur de jeu.

    Cette opération n'est volontairement exposée à aucun endpoint client : le
    moteur serveur devra être le seul à pouvoir certifier un résultat.
    """
    with transaction.atomic():
        game = _lock_game(game_id)
        if game.status != Game.Status.ACTIVE:
            raise GameConflict("Seule une partie en cours peut être finalisée.")
        participants = list(
            GameParticipant.objects.select_for_update()
            .filter(game=game)
            .order_by("seat_number")
        )
        by_id = {str(participant.pk): participant for participant in participants}
        normalized_kilometers = {
            str(participant_id): value
            for participant_id, value in kilometers_by_participant.items()
        }
        if set(normalized_kilometers) != set(by_id):
            raise ValidationError(
                "Un nombre de kilomètres doit être fourni pour chaque participant."
            )
        for participant_id, kilometers in normalized_kilometers.items():
            if (
                not isinstance(kilometers, int)
                or isinstance(kilometers, bool)
                or kilometers < 0
                or kilometers > 1000
            ):
                raise ValidationError("Les kilomètres doivent être compris entre 0 et 1000.")
            by_id[participant_id].kilometers = kilometers
            by_id[participant_id].save(update_fields=["kilometers"])

        winner = by_id.get(str(winner_participant_id))
        if winner is None:
            raise ValidationError("Le gagnant doit être un participant de la partie.")
        winner.placement = 1
        winner.save(update_fields=["placement"])

        game.status = Game.Status.FINISHED
        game.finished_at = timezone.now()
        game.save(update_fields=["status", "finished_at", "updated_at"])
        GameResult.objects.create(game=game, winner=winner)

        for participant in participants:
            if participant.user_id is None:
                continue
            stats, _ = PlayerStats.objects.get_or_create(user_id=participant.user_id)
            PlayerStats.objects.filter(pk=stats.pk).update(
                games_played=F("games_played") + 1,
                wins=F("wins") + int(participant.pk == winner.pk),
                total_kilometers=F("total_kilometers") + participant.kilometers,
                best_kilometers=Greatest(
                    F("best_kilometers"), Value(participant.kilometers)
                ),
            )
        record_game_event(
            game,
            "game.finished",
            actor=None,
            public_payload={
                "winner_participant_id": str(winner.pk),
                "kilometers": {
                    str(participant.pk): participant.kilometers
                    for participant in participants
                },
            },
        )
    return game
