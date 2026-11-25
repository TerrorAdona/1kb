"""Pure, deterministic game transitions and legality checks."""

from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from .cards import Card, CardCategory, CardType, build_deck
from .models import GamePhase, GameState, PlayerState, RulesConfig


class ActionType(str, Enum):
    DRAW = "draw"
    PLAY = "play"
    DISCARD = "discard"
    PASS = "pass"


class RuleViolation(ValueError):
    """A command is invalid for the authoritative game state."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class LegalPlay:
    card_id: str
    target_player_id: str | None = None
    is_coup_fourre: bool = False


@dataclass(frozen=True, slots=True)
class EngineEvent:
    event_type: str
    actor_player_id: str
    card_id: str | None = None
    card_type: str | None = None
    target_player_id: str | None = None
    private_to_player_id: str | None = None
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Transition:
    state: GameState
    events: tuple[EngineEvent, ...]


ATTACK_TO_PARADE: dict[CardType, CardType] = {
    CardType.RED_LIGHT: CardType.GREEN_LIGHT,
    CardType.OUT_OF_FUEL: CardType.FUEL,
    CardType.FLAT_TIRE: CardType.SPARE_TIRE,
    CardType.ACCIDENT: CardType.REPAIRS,
}

ATTACK_TO_SAFETY: dict[CardType, CardType] = {
    CardType.RED_LIGHT: CardType.PRIORITY_VEHICLE,
    CardType.SPEED_LIMIT: CardType.PRIORITY_VEHICLE,
    CardType.OUT_OF_FUEL: CardType.EXTRA_TANK,
    CardType.FLAT_TIRE: CardType.PUNCTURE_PROOF,
    CardType.ACCIDENT: CardType.DRIVING_ACE,
}

SAFETY_TO_ATTACKS: dict[CardType, frozenset[CardType]] = {
    CardType.PRIORITY_VEHICLE: frozenset(
        {CardType.RED_LIGHT, CardType.SPEED_LIMIT}
    ),
    CardType.EXTRA_TANK: frozenset({CardType.OUT_OF_FUEL}),
    CardType.PUNCTURE_PROOF: frozenset({CardType.FLAT_TIRE}),
    CardType.DRIVING_ACE: frozenset({CardType.ACCIDENT}),
}

def new_game(
    player_ids: Sequence[str],
    *,
    rules: RulesConfig | None = None,
    seed: int | None = None,
    deck: Sequence[Card] | None = None,
    first_player_index: int = 0,
) -> GameState:
    """Create a game and deal the initial hand.

    ``deck`` is an optional, already ordered shoe (top card first), intended for
    deterministic tests and controlled simulations. Production callers should
    omit it and let the engine securely shuffle its generated deck.
    """
    rules = rules or RulesConfig()
    normalized_ids = [str(player_id) for player_id in player_ids]
    if not 2 <= len(normalized_ids) <= rules.max_players:
        raise ValueError(f"Une partie exige de 2 à {rules.max_players} joueurs.")
    if len(set(normalized_ids)) != len(normalized_ids):
        raise ValueError("Les identifiants joueurs doivent être uniques.")
    if not 0 <= first_player_index < len(normalized_ids):
        raise ValueError("first_player_index ne correspond à aucun joueur.")

    cards = list(deck) if deck is not None else build_deck()
    if deck is None:
        if seed is None:
            random.SystemRandom().shuffle(cards)
        else:
            random.Random(seed).shuffle(cards)

    needed = len(normalized_ids) * rules.initial_hand_size
    if len(cards) < needed:
        raise ValueError("La pioche ne contient pas assez de cartes pour la donne.")

    players = [PlayerState(player_id=player_id) for player_id in normalized_ids]
    for _ in range(rules.initial_hand_size):
        for player in players:
            player.hand.append(cards.pop(0))

    return GameState(
        players=players,
        draw_pile=cards,
        discard_pile=[],
        active_player_index=first_player_index,
        phase=GamePhase.DRAW,
        rules=rules,
    )


def legal_plays(state: GameState, player_id: str) -> tuple[LegalPlay, ...]:
    """List currently legal plays as a UI/AI hint; never trust it as validation."""
    player = _find_player(state, str(player_id))
    if state.phase == GamePhase.RESPONSE:
        if player.player_id != state.pending_response_player_id:
            return ()
        attack = state.pending_response_attack
        if attack is None:
            return ()
        safety = ATTACK_TO_SAFETY.get(attack.card_type)
        return tuple(
            LegalPlay(card.id, is_coup_fourre=True)
            for card in player.hand
            if safety == card.card_type and card.card_type not in player.safeties
        )

    if state.phase != GamePhase.ACTION or player.player_id != state.active_player.player_id:
        return ()

    plays: list[LegalPlay] = []
    for card in player.hand:
        category = card.category
        if category == CardCategory.DISTANCE and _can_play_distance(state, player, card):
            plays.append(LegalPlay(card.id))
        elif category == CardCategory.PARADE and _can_play_parade(state, player, card):
            plays.append(LegalPlay(card.id))
        elif category == CardCategory.SAFETY and card.card_type not in player.safeties:
            plays.append(LegalPlay(card.id))
        elif category == CardCategory.ATTACK:
            for target in state.players:
                if target.player_id != player.player_id and _can_attack(
                    target, card.card_type
                ):
                    plays.append(LegalPlay(card.id, target.player_id))
    return tuple(plays)


def apply_action(
    state: GameState,
    *,
    player_id: str,
    action: ActionType | str,
    card_id: str | None = None,
    target_player_id: str | None = None,
) -> Transition:
    """Validate and apply one command without mutating the supplied state."""
    try:
        action_type = ActionType(action)
    except (TypeError, ValueError) as exc:
        raise RuleViolation("invalid_action", "Action inconnue.") from exc

    if state.phase == GamePhase.FINISHED:
        raise RuleViolation("game_finished", "La partie est déjà terminée.")

    actor_id = str(player_id)
    next_state = deepcopy(state)
    events: list[EngineEvent] = []

    if next_state.phase == GamePhase.RESPONSE:
        return _apply_response_action(
            next_state,
            actor_id=actor_id,
            action=action_type,
            card_id=card_id,
            events=events,
        )

    active = next_state.active_player
    if actor_id != active.player_id:
        raise RuleViolation("not_your_turn", "Ce n’est pas votre tour.")

    if next_state.phase == GamePhase.DRAW:
        if action_type != ActionType.DRAW:
            raise RuleViolation("draw_required", "Vous devez d’abord piocher.")
        card = _draw_one(next_state)
        next_state.phase = GamePhase.ACTION
        if card is None:
            events.append(
                EngineEvent(
                    event_type="draw.empty",
                    actor_player_id=actor_id,
                    private_to_player_id=actor_id,
                )
            )
        else:
            events.append(
                EngineEvent(
                    event_type="card.drawn",
                    actor_player_id=actor_id,
                    card_id=card.id,
                    card_type=card.card_type.value,
                    private_to_player_id=actor_id,
                )
            )
        return Transition(next_state, tuple(events))

    if action_type == ActionType.DRAW:
        raise RuleViolation("already_drew", "La pioche de ce tour a déjà eu lieu.")

    if action_type == ActionType.PASS:
        raise RuleViolation("no_response_pending", "Aucune attaque ne doit être parée.")

    if action_type == ActionType.DISCARD:
        _discard_card(next_state, actor_id, card_id)
        _complete_turn(next_state)
        events.append(
            EngineEvent(
                event_type="card.discarded",
                actor_player_id=actor_id,
                card_id=card_id,
                card_type=_card_type_value(next_state.discard_pile[-1]),
            )
        )
        _finish_if_needed(next_state, events, actor_id)
        return Transition(next_state, tuple(events))

    card = _get_owned_card(active, card_id)
    if card.category == CardCategory.DISTANCE:
        _play_distance(next_state, active, card)
        events.append(_card_event("distance.played", actor_id, card))
        _finish_if_exact_distance(next_state, active, events)
        if next_state.phase != GamePhase.FINISHED:
            _complete_turn(next_state)
            _finish_if_needed(next_state, events, actor_id)
    elif card.category == CardCategory.ATTACK:
        if not target_player_id:
            raise RuleViolation("target_required", "Choisissez un joueur à attaquer.")
        target = _find_player(next_state, str(target_player_id))
        _play_attack(next_state, active, target, card)
        events.append(
            _card_event("attack.played", actor_id, card, target_player_id=target.player_id)
        )
        next_state.phase = GamePhase.RESPONSE
        next_state.pending_response_player_id = target.player_id
        next_state.pending_response_attack = card
    elif card.category == CardCategory.PARADE:
        _play_parade(next_state, active, card)
        if active.green_light_card is not card:
            next_state.discard_pile.append(card)
        events.append(_card_event("parade.played", actor_id, card))
        _complete_turn(next_state)
        _finish_if_needed(next_state, events, actor_id)
    else:
        _play_safety(next_state, active, card)
        events.append(_card_event("safety.played", actor_id, card))
        # A safety grants an immediate replay and a replacement draw.
        drawn = _draw_one(next_state)
        if drawn is not None:
            events.append(
                EngineEvent(
                    event_type="card.drawn",
                    actor_player_id=actor_id,
                    card_id=drawn.id,
                    card_type=drawn.card_type.value,
                    private_to_player_id=actor_id,
                    details={"reason": "safety_replay"},
                )
            )
    return Transition(next_state, tuple(events))


def score_player(state: GameState, player_id: str) -> int:
    """The 2025 notice defines race results by distance, not cumulative points."""
    return _find_player(state, str(player_id)).distance


def calculate_scores(state: GameState) -> dict[str, int]:
    """Return each seat's current race score, expressed as kilometers."""
    return {player.player_id: player.distance for player in state.players}


def _apply_response_action(
    state: GameState,
    *,
    actor_id: str,
    action: ActionType,
    card_id: str | None,
    events: list[EngineEvent],
) -> Transition:
    if actor_id != state.pending_response_player_id:
        raise RuleViolation(
            "not_response_player",
            "Seul le joueur attaqué peut répondre à cette attaque.",
        )
    if action == ActionType.PASS:
        attacker_id = state.active_player.player_id
        state.phase = GamePhase.DRAW
        state.pending_response_player_id = None
        state.pending_response_attack = None
        _complete_turn(state)
        events.append(
            EngineEvent(event_type="coup_fourre.passed", actor_player_id=actor_id)
        )
        _finish_if_needed(state, events, attacker_id)
        return Transition(state, tuple(events))

    if action != ActionType.PLAY:
        raise RuleViolation(
            "response_only",
            "Vous pouvez uniquement tenter un Coup-Fourré ou laisser passer.",
        )

    player = _find_player(state, actor_id)
    card = _get_owned_card(player, card_id)
    pending = state.pending_response_attack
    matching_safety = ATTACK_TO_SAFETY.get(pending.card_type) if pending else None
    if card.category != CardCategory.SAFETY or card.card_type != matching_safety:
        raise RuleViolation(
            "invalid_coup_fourre",
            "Cette Botte ne correspond pas à l’attaque subie.",
        )
    if card.card_type in player.safeties:
        raise RuleViolation("safety_already_played", "Cette Botte est déjà active.")

    player.hand.remove(card)
    _activate_safety_and_clear(state, player, card.card_type)
    player.coup_fourres += 1
    state.pending_response_player_id = None
    state.pending_response_attack = None
    state.active_player_index = state.players.index(player)
    state.phase = GamePhase.ACTION

    events.append(
        _card_event(
            "coup_fourre.played",
            actor_id,
            card,
            target_player_id=actor_id,
            details={"distance_bonus": 0},
        )
    )
    # The first draw restores the hand after the off-turn safety; the second
    # draw is the immediate replay granted by the Coup-Fourré.
    for reason in ("coup_fourre_refill", "coup_fourre_replay"):
        drawn = _draw_one(state)
        if drawn is not None:
            events.append(
                EngineEvent(
                    event_type="card.drawn",
                    actor_player_id=actor_id,
                    card_id=drawn.id,
                    card_type=drawn.card_type.value,
                    private_to_player_id=actor_id,
                    details={"reason": reason},
                )
            )
    return Transition(state, tuple(events))


def _can_play_distance(state: GameState, player: PlayerState, card: Card) -> bool:
    distance = card.distance_km
    if distance is None:
        return False
    if player.battle_attack is not None:
        return False
    if player.must_play_green_light and card.card_type != CardType.GREEN_LIGHT:
        return False
    if (
        state.rules.start_requires_green_light
        and not player.has_rolled
        and not player.has_green_light
        and CardType.PRIORITY_VEHICLE not in player.safeties
    ):
        return False
    if (
        player.is_speed_limited
        and distance > state.rules.speed_limit_max
    ):
        return False
    if (
        card.card_type == CardType.KM_200
        and player.count_200_cards >= state.rules.max_200_cards
    ):
        return False
    if player.distance + distance > state.rules.target_distance:
        return False
    return True


def _can_play_parade(state: GameState, player: PlayerState, card: Card) -> bool:
    if card.card_type == CardType.GREEN_LIGHT:
        if player.battle_attack and player.battle_attack.card_type == CardType.RED_LIGHT:
            return True
        if player.must_play_green_light:
            return True
        return (
            state.rules.start_requires_green_light
            and not player.has_rolled
            and not player.has_green_light
            and player.battle_attack is None
        )
    if card.card_type == CardType.END_SPEED_LIMIT:
        return player.speed_attack is not None
    return (
        player.battle_attack is not None
        and ATTACK_TO_PARADE.get(player.battle_attack.card_type) == card.card_type
    )


def _can_attack(
    target: PlayerState,
    card_type: CardType,
) -> bool:
    if card_type == CardType.SPEED_LIMIT:
        return (
            target.speed_attack is None
            and CardType.PRIORITY_VEHICLE not in target.safeties
        )
    if card_type not in ATTACK_TO_PARADE:
        return False
    safety = ATTACK_TO_SAFETY[card_type]
    return (
        target.has_rolled
        and target.battle_attack is None
        and safety not in target.safeties
    )


def _play_distance(state: GameState, player: PlayerState, card: Card) -> None:
    if card not in player.hand:
        raise RuleViolation("card_not_in_hand", "Cette carte n’est pas dans votre main.")
    if not _can_play_distance(state, player, card):
        if player.battle_attack:
            raise RuleViolation("vehicle_stopped", "Vous devez d’abord parer l’attaque.")
        if player.must_play_green_light:
            raise RuleViolation("green_light_required", "Vous devez jouer un Feu Vert.")
        if player.is_speed_limited and (card.distance_km or 0) > state.rules.speed_limit_max:
            raise RuleViolation(
                "speed_limit",
                f"La Limite de Vitesse interdit les cartes supérieures à "
                f"{state.rules.speed_limit_max} km.",
            )
        if card.card_type == CardType.KM_200 and (
            player.count_200_cards >= state.rules.max_200_cards
        ):
            raise RuleViolation("too_many_200_cards", "Maximum de cartes 200 km atteint.")
        if player.distance + (card.distance_km or 0) > state.rules.target_distance:
            raise RuleViolation("distance_exceeded", "Cette carte ferait dépasser l’objectif.")
        if (
            not player.has_rolled
            and state.rules.start_requires_green_light
            and not player.has_green_light
            and CardType.PRIORITY_VEHICLE not in player.safeties
        ):
            raise RuleViolation("green_light_required", "Vous devez d’abord jouer un Feu Vert.")
        raise RuleViolation("invalid_distance_card", "Cette carte Borne ne peut pas être jouée.")

    player.hand.remove(card)
    player.distance_cards.append(card)
    player.must_play_green_light = False


def _play_attack(
    state: GameState,
    attacker: PlayerState,
    target: PlayerState,
    card: Card,
) -> None:
    if target.player_id == attacker.player_id:
        raise RuleViolation("self_attack", "Vous ne pouvez pas vous attaquer vous-même.")
    if card not in attacker.hand or card.category != CardCategory.ATTACK:
        raise RuleViolation("card_not_in_hand", "Cette carte Attaque n’est pas dans votre main.")
    if not _can_attack(target, card.card_type):
        if card.card_type == CardType.SPEED_LIMIT:
            raise RuleViolation(
                "speed_limit_unavailable",
                "Cette cible est déjà limitée ou protégée par le Véhicule Prioritaire.",
            )
        if not target.has_rolled:
            raise RuleViolation("target_not_rolling", "Cette cible n’a pas encore roulé.")
        if target.battle_attack is not None:
            raise RuleViolation("battle_attack_active", "Cette cible a déjà une attaque active.")
        raise RuleViolation("target_protected", "Cette cible est protégée contre cette attaque.")

    attacker.hand.remove(card)
    if (
        card.card_type != CardType.SPEED_LIMIT
        and target.green_light_card is not None
    ):
        state.discard_pile.append(target.green_light_card)
        target.green_light_card = None
    if card.card_type == CardType.SPEED_LIMIT:
        target.speed_attack = card
    else:
        target.battle_attack = card


def _play_parade(state: GameState, player: PlayerState, card: Card) -> None:
    if card not in player.hand or card.category != CardCategory.PARADE:
        raise RuleViolation("card_not_in_hand", "Cette carte Parade n’est pas dans votre main.")
    if not _can_play_parade(state, player, card):
        raise RuleViolation("parade_not_matching", "Cette Parade ne correspond à aucun danger actif.")

    player.hand.remove(card)
    if card.card_type == CardType.END_SPEED_LIMIT:
        state.discard_pile.append(player.speed_attack)
        player.speed_attack = None
    elif card.card_type == CardType.GREEN_LIGHT and (
        player.battle_attack is None
    ):
        # This is only legal in a ruleset where a Green Light is required to
        # start or resume; keep it as the player's visible battle-pile card.
        player.green_light_card = card
        player.must_play_green_light = False
    else:
        old_attack = player.battle_attack
        state.discard_pile.append(old_attack)
        player.battle_attack = None
        if card.card_type == CardType.GREEN_LIGHT:
            player.green_light_card = card
        if (
            state.rules.require_green_after_repair
            and card.card_type != CardType.GREEN_LIGHT
            and CardType.PRIORITY_VEHICLE not in player.safeties
        ):
            player.must_play_green_light = True


def _play_safety(state: GameState, player: PlayerState, card: Card) -> None:
    if card not in player.hand or card.category != CardCategory.SAFETY:
        raise RuleViolation("card_not_in_hand", "Cette carte Botte n’est pas dans votre main.")
    if card.card_type in player.safeties:
        raise RuleViolation("safety_already_played", "Cette Botte est déjà active.")
    player.hand.remove(card)
    _activate_safety_and_clear(state, player, card.card_type)


def _activate_safety_and_clear(
    state: GameState,
    player: PlayerState,
    card_type: CardType,
) -> None:
    _activate_safety(player, card_type)
    covered_attacks = SAFETY_TO_ATTACKS[card_type]
    if player.battle_attack and player.battle_attack.card_type in covered_attacks:
        state.discard_pile.append(player.battle_attack)
        player.battle_attack = None
    if player.speed_attack and player.speed_attack.card_type in covered_attacks:
        state.discard_pile.append(player.speed_attack)
        player.speed_attack = None
    if card_type == CardType.PRIORITY_VEHICLE or player.battle_attack is None:
        player.must_play_green_light = False


def _activate_safety(player: PlayerState, card_type: CardType) -> None:
    player.safeties.add(card_type)


def _discard_card(state: GameState, player_id: str, card_id: str | None) -> None:
    if not card_id:
        raise RuleViolation("card_required", "Indiquez la carte à défausser.")
    player = _find_player(state, player_id)
    card = _get_owned_card(player, card_id)
    if not state.rules.allow_voluntary_discard and legal_plays(state, player_id):
        raise RuleViolation(
            "discard_not_allowed",
            "Vous ne pouvez défausser que si aucune carte n’est jouable.",
        )
    player.hand.remove(card)
    state.discard_pile.append(card)


def _get_owned_card(player: PlayerState, card_id: str | None) -> Card:
    if not card_id:
        raise RuleViolation("card_required", "Indiquez la carte à jouer.")
    card = next((card for card in player.hand if card.id == str(card_id)), None)
    if card is None:
        raise RuleViolation("card_not_in_hand", "Cette carte n’est pas dans votre main.")
    return card


def _find_player(state: GameState, player_id: str) -> PlayerState:
    player = next((p for p in state.players if p.player_id == str(player_id)), None)
    if player is None:
        raise RuleViolation("unknown_player", "Ce joueur ne participe pas à la partie.")
    return player


def _draw_one(state: GameState) -> Card | None:
    if not state.draw_pile:
        return None
    card = state.draw_pile.pop(0)
    state.players[state.active_player_index].hand.append(card)
    return card


def _complete_turn(state: GameState) -> None:
    state.active_player_index = (state.active_player_index + 1) % len(state.players)
    state.turn_number += 1
    state.phase = GamePhase.DRAW
    state.pending_response_player_id = None
    state.pending_response_attack = None


def _finish_if_exact_distance(
    state: GameState,
    player: PlayerState,
    events: list[EngineEvent],
) -> None:
    if player.distance == state.rules.target_distance:
        _finish(state, [player.player_id], "target_distance")
        events.append(
            EngineEvent(
                event_type="game.finished",
                actor_player_id=player.player_id,
                details={"winner_ids": list(state.winner_ids), "reason": state.finish_reason},
            )
        )


def _finish_if_needed(
    state: GameState,
    events: list[EngineEvent],
    actor_id: str,
) -> None:
    if state.phase == GamePhase.FINISHED or not state.rules.end_when_no_distance_cards:
        return
    if any(card.category == CardCategory.DISTANCE for card in state.draw_pile):
        return
    best_distance = max(player.distance for player in state.players)
    winners = [
        player.player_id
        for player in state.players
        if player.distance == best_distance
    ]
    _finish(state, winners, "distance_pile_empty")
    events.append(
        EngineEvent(
            event_type="game.finished",
            actor_player_id=actor_id,
            details={
                "winner_ids": list(state.winner_ids),
                "reason": state.finish_reason,
                "scores": {player.player_id: player.distance for player in state.players},
            },
        )
    )


def _finish(state: GameState, winner_ids: list[str], reason: str) -> None:
    state.phase = GamePhase.FINISHED
    state.winner_ids = list(winner_ids)
    state.finish_reason = reason
    state.pending_response_player_id = None
    state.pending_response_attack = None


def _card_event(
    event_type: str,
    actor_id: str,
    card: Card,
    *,
    target_player_id: str | None = None,
    details: dict[str, object] | None = None,
) -> EngineEvent:
    return EngineEvent(
        event_type=event_type,
        actor_player_id=actor_id,
        card_id=card.id,
        card_type=card.card_type.value,
        target_player_id=target_player_id,
        details=details or {},
    )


def _card_type_value(card: Card) -> str:
    return card.card_type.value
