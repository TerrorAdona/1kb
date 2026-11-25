"""Build a strategy view without exposing opponent hands or deck contents."""

from __future__ import annotations

from collections import Counter

from domain.game_engine import CARD_CATALOG, CardType, GameState, PlayerState

from .models import GameObservation, PlayerObservation


def _public_player(player: PlayerState) -> PlayerObservation:
    return PlayerObservation(
        player_id=player.player_id,
        hand_size=len(player.hand),
        distance=player.distance,
        battle_attack=player.battle_attack.card_type if player.battle_attack else None,
        speed_attack=player.speed_attack.card_type if player.speed_attack else None,
        green_light_active=player.green_light_card is not None,
        must_play_green_light=player.must_play_green_light,
        safeties=frozenset(player.safeties),
        count_200_cards=player.count_200_cards,
    )


def build_observation(state: GameState, player_id: str) -> GameObservation:
    """Project authoritative state into information available to one player.

    This is the only AI module that accepts ``GameState``. Strategy classes
    receive this projection and engine-generated legal plays instead.
    """
    player_id = str(player_id)
    player = next((item for item in state.players if item.player_id == player_id), None)
    if player is None:
        raise ValueError("Le joueur de l’observation ne participe pas à la partie.")

    known_public = Counter(card.card_type for card in state.discard_pile)
    for board_player in state.players:
        known_public.update(card.card_type for card in board_player.distance_cards)
        for exposed in (
            board_player.battle_attack,
            board_player.speed_attack,
            board_player.green_light_card,
        ):
            if exposed is not None:
                known_public[exposed.card_type] += 1
        known_public.update(board_player.safeties)

    hand_counts = Counter(card.card_type for card in player.hand)
    unseen_counts = tuple(
        (
            card_type,
            max(0, definition.quantity - known_public[card_type] - hand_counts[card_type]),
        )
        for card_type, definition in CARD_CATALOG.items()
    )

    return GameObservation(
        player_id=player_id,
        phase=state.phase,
        active_player_id=state.active_player.player_id,
        pending_response_player_id=state.pending_response_player_id,
        pending_response_attack=(
            state.pending_response_attack.card_type
            if state.pending_response_attack
            else None
        ),
        player=_public_player(player),
        hand=tuple(player.hand),
        opponents=tuple(
            _public_player(other)
            for other in state.players
            if other.player_id != player_id
        ),
        draw_pile_count=len(state.draw_pile),
        discard_pile=tuple(card.card_type for card in state.discard_pile),
        unseen_card_counts=unseen_counts,
        target_distance=state.rules.target_distance,
        speed_limit_max=state.rules.speed_limit_max,
        max_200_cards=state.rules.max_200_cards,
        allow_voluntary_discard=state.rules.allow_voluntary_discard,
    )
