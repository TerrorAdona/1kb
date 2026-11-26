import asyncio
import hashlib
import hmac
import random
import secrets
from collections.abc import Callable, Mapping
from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.db.models import Count, F, Value
from django.db.models.functions import Greatest
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.statistics.models import PlayerStats
from domain.game_ai import AIConfig, Difficulty
from domain.game_ai.observation import build_observation
from domain.game_ai.runner import drive_automatic_turn
from domain.game_ai.strategies import choose_action
from domain.game_engine.engine import (
    RuleViolation,
    Transition,
    apply_action,
    legal_plays,
    new_game,
)
from domain.game_engine.models import GamePhase, GameState, state_from_dict, state_to_dict

from .events import record_game_event
from .models import Game, GameEvent, GameParticipant, GameResult

INVITE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class GameConflict(APIException):
    status_code = 409
    default_detail = "La partie ne peut pas effectuer cette action dans son état actuel."
    default_code = "game_conflict"


class GameActionRejected(APIException):
    status_code = 400
    default_detail = "Cette action n’est pas autorisée."
    default_code = "invalid_game_action"

    def __init__(self, detail=None, code=None):
        super().__init__(detail or self.default_detail, code or self.default_code)


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


def create_game(
    *,
    host: User,
    mode: str,
    visibility: str,
    max_players: int,
    invite_expires_in_hours: int,
    bot_difficulty: str = Difficulty.NORMAL.value,
):
    if mode == Game.Mode.SOLO:
        visibility = Game.Visibility.PRIVATE
        try:
            bot_difficulty = Difficulty(bot_difficulty).value
        except ValueError as exc:
            raise ValidationError("Difficulté de bot inconnue.") from exc

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
                    bot_difficulty=bot_difficulty,
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
        if game.status == Game.Status.ACTIVE:
            participant = _participant(game, user)
            if participant.abandoned_at is None:
                participant.abandoned_at = timezone.now()
                participant.save(update_fields=["abandoned_at"])
                game.status = Game.Status.CANCELLED
                game.save(update_fields=["status", "updated_at"])
                record_game_event(
                    game,
                    "player.abandoned",
                    actor=user,
                    public_payload={
                        "participant_id": str(participant.pk),
                        "display_name": participant.display_name,
                        "game_cancelled": True,
                    },
                )
            return game
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
        # The engine snapshot is the authoritative state for both modes. Bots
        # remain in their existing seats, so initializing the solo state does
        # not change its room or AI configuration.
        engine_state = new_game([str(p.pk) for p in participants])
        game.state = state_to_dict(engine_state)
        game.status = Game.Status.ACTIVE
        game.started_at = timezone.now()
        game.save(update_fields=["state", "status", "started_at", "updated_at"])
        record_game_event(
            game,
            "game.started",
            actor=user,
            public_payload={
                "active_player_id": str(participants[engine_state.active_player_index].pk),
                "phase": engine_state.phase.value,
            },
        )
    return game


def abandon_multiplayer_game(*, game_id, user: User, request_id: UUID):
    """Record an explicit concession and cancel the match without losing state."""
    command = {"type": "game.abandon"}
    with transaction.atomic():
        game = _lock_game(game_id)
        participant = _participant(game, user)
        previous = GameEvent.objects.filter(
            game=game, actor=user, request_id=request_id
        ).first()
        if previous:
            if previous.public_payload.get("client_action") != command:
                raise GameConflict("Cet identifiant de commande a déjà été utilisé.")
            return game, True
        if game.mode != Game.Mode.MULTIPLAYER:
            raise GameConflict("L’abandon WebSocket est réservé au multijoueur.")
        if game.status != Game.Status.ACTIVE:
            raise GameConflict("Seule une partie en cours peut être abandonnée.")
        if participant.abandoned_at is None:
            participant.abandoned_at = timezone.now()
            participant.save(update_fields=["abandoned_at"])
        game.status = Game.Status.CANCELLED
        game.save(update_fields=["status", "updated_at"])
        record_game_event(
            game,
            "player.abandoned",
            actor=user,
            public_payload={
                "client_action": command,
                "participant_id": str(participant.pk),
                "display_name": participant.display_name,
                "game_cancelled": True,
            },
            request_id=request_id,
        )
        return game, False


def apply_multiplayer_action(
    *,
    game_id,
    user: User,
    request_id: UUID,
    expected_version: int,
    action: str,
    card_id: str | None = None,
    target_player_id: str | None = None,
):
    """Validate, apply and persist one player command atomically.

    The client supplies intent only. The engine state, acting seat and result
    are all loaded and validated on the server while the game row is locked.
    """
    command = {
        "action": action,
        "card_id": card_id,
        "target_player_id": target_player_id,
    }
    with transaction.atomic():
        game = _lock_game(game_id)
        participant = _participant(game, user)

        previous = GameEvent.objects.filter(
            game=game, actor=user, request_id=request_id
        ).first()
        if previous:
            if previous.public_payload.get("client_action") != command:
                raise GameConflict("Cet identifiant de commande a déjà été utilisé.")
            return game, True

        if game.mode != Game.Mode.MULTIPLAYER:
            raise GameConflict("Les commandes WebSocket sont réservées au multijoueur.")
        if game.status != Game.Status.ACTIVE:
            raise GameConflict("Cette partie n’accepte plus de coups.")
        if (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version != game.state_version
        ):
            raise GameConflict(
                "L’état de la partie a changé. Reconnectez-vous pour obtenir le nouvel état."
            )
        if not isinstance(game.state, dict) or not game.state.get("players"):
            raise GameConflict("L’état de la partie est indisponible.")

        try:
            current_state = state_from_dict(game.state)
            transition = apply_action(
                current_state,
                player_id=str(participant.pk),
                action=action,
                card_id=card_id,
                target_player_id=target_player_id,
            )
        except RuleViolation as exc:
            raise GameActionRejected(str(exc), exc.code) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise GameConflict("L’état enregistré de la partie est invalide.") from exc

        game.state = state_to_dict(transition.state)
        game.save(update_fields=["state", "updated_at"])

        participants = list(
            GameParticipant.objects.select_for_update()
            .filter(game=game)
            .order_by("seat_number")
        )
        participants_by_id = {str(item.pk): item for item in participants}
        for engine_player in transition.state.players:
            db_player = participants_by_id.get(engine_player.player_id)
            if db_player is None:
                raise GameConflict("Le moteur référence un siège inexistant.")
            if db_player.kilometers != engine_player.distance:
                db_player.kilometers = engine_player.distance
                db_player.save(update_fields=["kilometers"])

        public_events = []
        private_events = {}
        for engine_event in transition.events:
            item = {
                "event_type": engine_event.event_type,
                "actor_player_id": engine_event.actor_player_id,
                "target_player_id": engine_event.target_player_id,
                "details": engine_event.details,
            }
            if engine_event.private_to_player_id:
                private_recipient = participants_by_id.get(
                    engine_event.private_to_player_id
                )
                if private_recipient and private_recipient.user_id:
                    private_item = {
                        **item,
                        "card_id": engine_event.card_id,
                        "card_type": engine_event.card_type,
                    }
                    private_events.setdefault(str(private_recipient.user_id), []).append(
                        private_item
                    )
            else:
                item.update(
                    card_id=engine_event.card_id,
                    card_type=engine_event.card_type,
                )
            # The event itself (e.g. “a pioché”) is public; only the identity
            # of a privately drawn card is withheld from the other seats.
            public_events.append(item)

        record_game_event(
            game,
            "game.action",
            actor=user,
            public_payload={
                "client_action": command,
                "action": action,
                "events": public_events,
            },
            private_payloads={
                user_id: {"events": events}
                for user_id, events in private_events.items()
            },
            request_id=request_id,
        )

        if transition.state.phase == GamePhase.FINISHED:
            winner_id = (
                transition.state.winner_ids[0]
                if transition.state.winner_ids
                else max(
                    transition.state.players,
                    key=lambda player: player.distance,
                ).player_id
            )
            finish_game(
                game_id=game.pk,
                winner_participant_id=winner_id,
                kilometers_by_participant={
                    str(item.pk): item.kilometers for item in participants
                },
            )

        game.refresh_from_db()
        return game, False


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
            is_winner = participant.pk == winner.pk
            PlayerStats.objects.filter(pk=stats.pk).update(
                games_played=F("games_played") + 1,
                wins=F("wins") + int(is_winner),
                losses=F("losses") + int(not is_winner),
                total_kilometers=F("total_kilometers") + participant.kilometers,
                best_kilometers=Greatest(
                    F("best_kilometers"), Value(participant.kilometers)
                ),
                solo_games_played=F("solo_games_played")
                + int(game.mode == Game.Mode.SOLO),
                multiplayer_games_played=F("multiplayer_games_played")
                + int(game.mode == Game.Mode.MULTIPLAYER),
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


def _run_bot_turn_sync(
    state: GameState,
    bot_configs: Mapping[str, AIConfig],
    player_id: str,
    on_transition: Callable[[Transition], None],
) -> GameState:
    """Synchronous wrapper to run a single bot turn without async context issues.

    This avoids the Django SynchronousOnlyOperation error by not using
    asyncio for the actual bot decision making - the strategy is pure sync.
    """
    config = bot_configs[player_id]
    random_source = random.Random(config.seed)
    current = state

    while True:
        if current.phase == GamePhase.FINISHED:
            return current
        active_id = (
            current.pending_response_player_id
            if current.phase == GamePhase.RESPONSE
            else current.active_player.player_id
        )
        if active_id != player_id:
            return current

        observation = build_observation(current, player_id)
        command = choose_action(
            observation,
            legal_plays(current, player_id),
            difficulty=config.difficulty,
            rng=random_source,
        )
        transition = apply_action(
            current,
            player_id=player_id,
            **command.to_engine_kwargs(),
        )
        current = transition.state
        on_transition(transition)


def apply_solo_action(
    *,
    game_id,
    user: User,
    request_id: UUID,
    expected_version: int,
    action: str,
    card_id: str | None = None,
    target_player_id: str | None = None,
):
    """Validate, apply and persist one player command in solo mode, then run AI turns.

    The client supplies intent only. The engine state, acting seat and result
    are all loaded and validated on the server while the game row is locked.
    After the human action, all bot turns are played automatically until the
    human player is the active player again or the game ends.
    """
    command = {
        "action": action,
        "card_id": card_id,
        "target_player_id": target_player_id,
    }
    with transaction.atomic():
        game = _lock_game(game_id)
        participant = _participant(game, user)

        previous = GameEvent.objects.filter(
            game=game, actor=user, request_id=request_id
        ).first()
        if previous:
            if previous.public_payload.get("client_action") != command:
                raise GameConflict("Cet identifiant de commande a déjà été utilisé.")
            return game, True

        if game.mode != Game.Mode.SOLO:
            raise GameConflict("Les commandes solo sont réservées au mode solo.")
        if game.status != Game.Status.ACTIVE:
            raise GameConflict("Cette partie n'accepte plus de coups.")
        if (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version != game.state_version
        ):
            raise GameConflict(
                "L'état de la partie a changé. Reconnectez-vous pour obtenir le nouvel état."
            )
        if not isinstance(game.state, dict) or not game.state.get("players"):
            raise GameConflict("L'état de la partie est indisponible.")

        try:
            current_state = state_from_dict(game.state)
            transition = apply_action(
                current_state,
                player_id=str(participant.pk),
                action=action,
                card_id=card_id,
                target_player_id=target_player_id,
            )
        except RuleViolation as exc:
            raise GameActionRejected(str(exc), exc.code) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise GameConflict("L'état enregistré de la partie est invalide.") from exc

        game.state = state_to_dict(transition.state)
        game.save(update_fields=["state", "updated_at"])

        participants = list(
            GameParticipant.objects.select_for_update()
            .filter(game=game)
            .order_by("seat_number")
        )
        participants_by_id = {str(item.pk): item for item in participants}

        # Build bot configurations for automatic play
        bot_configs = {
            str(bot.pk): AIConfig(difficulty=Difficulty(bot.bot_difficulty or Difficulty.NORMAL.value))
            for bot in participants
            if bot.kind == GameParticipant.Kind.BOT
        }

        # Helper to persist state, events, and update kilometers
        def persist_transition(trans_state, trans_events, actor_user_id=None):
            game.state = state_to_dict(trans_state)
            game.save(update_fields=["state", "updated_at"])

            for engine_player in trans_state.players:
                db_player = participants_by_id.get(engine_player.player_id)
                if db_player is None:
                    raise GameConflict("Le moteur référence un siège inexistant.")
                if db_player.kilometers != engine_player.distance:
                    db_player.kilometers = engine_player.distance
                    db_player.save(update_fields=["kilometers"])

            public_events = []
            private_events = {}
            for engine_event in trans_events:
                item = {
                    "event_type": engine_event.event_type,
                    "actor_player_id": engine_event.actor_player_id,
                    "target_player_id": engine_event.target_player_id,
                    "details": engine_event.details,
                }
                if engine_event.private_to_player_id:
                    private_recipient = participants_by_id.get(
                        engine_event.private_to_player_id
                    )
                    if private_recipient and private_recipient.user_id:
                        private_item = {
                            **item,
                            "card_id": engine_event.card_id,
                            "card_type": engine_event.card_type,
                        }
                        private_events.setdefault(str(private_recipient.user_id), []).append(
                            private_item
                        )
                else:
                    item.update(
                        card_id=engine_event.card_id,
                        card_type=engine_event.card_type,
                    )
                public_events.append(item)

            record_game_event(
                game,
                "game.action",
                actor=user if actor_user_id else None,
                public_payload={
                    "client_action": command if actor_user_id else {"type": "bot_action"},
                    "action": action if actor_user_id else "bot_play",
                    "events": public_events,
                },
                private_payloads={
                    user_id: {"events": events}
                    for user_id, events in private_events.items()
                },
                request_id=request_id if actor_user_id else None,
            )

        # Persist the human action first
        persist_transition(transition.state, transition.events, actor_user_id=user.pk)

        # Run automatic bot turns until it's the human's turn or game ends
        current_state = transition.state
        while current_state.phase != GamePhase.FINISHED:
            # Check if it's a bot's turn
            player_id = (
                current_state.pending_response_player_id
                if current_state.phase == GamePhase.RESPONSE
                else current_state.active_player.player_id
            )
            if player_id not in bot_configs:
                break  # Human's turn or no bots

            # Drive the bot's turn using a synchronous helper
            current_state = _run_bot_turn_sync(
                current_state,
                bot_configs,
                player_id,
                lambda t: persist_transition(t.state, t.events, actor_user_id=None),
            )

        # Check if game finished during bot turns
        if current_state.phase == GamePhase.FINISHED:
            winner_id = (
                current_state.winner_ids[0]
                if current_state.winner_ids
                else max(
                    current_state.players,
                    key=lambda player: player.distance,
                ).player_id
            )
            finish_game(
                game_id=game.pk,
                winner_participant_id=winner_id,
                kilometers_by_participant={
                    str(item.pk): item.kilometers for item in participants
                },
            )

        game.refresh_from_db()
        return game, False
