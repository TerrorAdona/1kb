"""Per-player WebSocket views of a persisted game."""

from apps.games.models import Game, GameEvent, GameParticipant
from apps.games.serializers import GameReadSerializer
from domain.game_engine.engine import legal_plays
from domain.game_engine.models import GamePhase, state_from_dict


def get_player_snapshot(*, game_id, user_id):
    """Return room metadata and a projection that never includes rival hands."""
    try:
        game = (
            Game.objects.select_related("host", "result__winner")
            .prefetch_related("participants")
            .get(pk=game_id)
        )
    except Game.DoesNotExist:
        return None

    participant = next(
        (
            item
            for item in game.participants.all()
            if item.user_id == user_id
        ),
        None,
    )
    if participant is None:
        return None

    result = {
        "game": GameReadSerializer(game).data,
        "state": None,
        "events": [],
    }

    if game.state and game.status in {
        Game.Status.ACTIVE,
        Game.Status.FINISHED,
        Game.Status.CANCELLED,
    }:
        engine_state = state_from_dict(game.state)
        visible_players = []
        for player in engine_state.players:
            db_participant = next(
                (
                    item
                    for item in game.participants.all()
                    if str(item.pk) == player.player_id
                ),
                None,
            )
            visible_players.append(
                {
                    "player_id": player.player_id,
                    "display_name": (
                        db_participant.display_name if db_participant else "Joueur"
                    ),
                    "seat_number": (
                        db_participant.seat_number if db_participant else None
                    ),
                    "distance": player.distance,
                    "distance_cards": [
                        card.to_dict() for card in player.distance_cards
                    ],
                    "hand_count": len(player.hand),
                    "battle_attack": (
                        player.battle_attack.to_dict()
                        if player.battle_attack
                        else None
                    ),
                    "speed_attack": (
                        player.speed_attack.to_dict()
                        if player.speed_attack
                        else None
                    ),
                    "green_light_card": (
                        player.green_light_card.to_dict()
                        if player.green_light_card
                        else None
                    ),
                    "safeties": sorted(
                        card_type.value for card_type in player.safeties
                    ),
                }
            )

        viewer_id = str(participant.pk)
        response_player_id = engine_state.pending_response_player_id
        may_respond = (
            engine_state.phase == GamePhase.RESPONSE
            and response_player_id == viewer_id
        )
        may_act = (
            engine_state.phase != GamePhase.RESPONSE
            and engine_state.phase != GamePhase.FINISHED
            and engine_state.active_player.player_id == viewer_id
        )
        legal_actions = (
            [
                {
                    "card_id": action.card_id,
                    "target_player_id": action.target_player_id,
                    "is_coup_fourre": action.is_coup_fourre,
                }
                for action in legal_plays(engine_state, viewer_id)
            ]
            if may_act or may_respond
            else []
        )
        result["state"] = {
            "viewer_player_id": viewer_id,
            "active_player_id": engine_state.active_player.player_id,
            "pending_response_player_id": response_player_id,
            "phase": engine_state.phase.value,
            "turn_number": engine_state.turn_number,
            "target_distance": engine_state.rules.target_distance,
            "draw_pile_count": len(engine_state.draw_pile),
            "discard_top": (
                engine_state.discard_pile[-1].to_dict()
                if engine_state.discard_pile
                else None
            ),
            "players": visible_players,
            "hand": [card.to_dict() for card in next(
                player for player in engine_state.players
                if player.player_id == viewer_id
            ).hand],
            "legal_actions": legal_actions,
            "can_draw": may_act and engine_state.phase == GamePhase.DRAW,
            "can_discard": (
                may_act
                and engine_state.phase == GamePhase.ACTION
                and (
                    engine_state.rules.allow_voluntary_discard
                    or not legal_actions
                )
            ),
            "can_pass": may_respond,
            "winner_ids": list(engine_state.winner_ids),
            "finish_reason": engine_state.finish_reason,
        }

    events = list(
        GameEvent.objects.filter(game=game)
        .order_by("-sequence")[:20]
    )
    result["events"] = [
        {
            "id": str(event.pk),
            "sequence": event.sequence,
            "event_type": event.event_type,
            "actor_display_name": event.actor_display_name,
            "data": event.public_payload,
            "private": event.private_payloads.get(str(user_id), {}),
            "created_at": event.created_at.isoformat(),
        }
        for event in reversed(events)
    ]
    return result


def get_participant_id(*, game_id, user_id):
    return (
        GameParticipant.objects.filter(game_id=game_id, user_id=user_id)
        .values_list("pk", flat=True)
        .first()
    )
