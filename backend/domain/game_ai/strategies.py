"""Easy, normal and hard strategies over sanitized observations."""

from __future__ import annotations

import random
from typing import Protocol, Sequence

from domain.game_engine import (
    ActionType,
    Card,
    CardCategory,
    CardType,
    GamePhase,
    LegalPlay,
)

from .models import AIAction, Difficulty, GameObservation


_PARADE_FOR_ATTACK = {
    CardType.RED_LIGHT: CardType.GREEN_LIGHT,
    CardType.OUT_OF_FUEL: CardType.FUEL,
    CardType.FLAT_TIRE: CardType.SPARE_TIRE,
    CardType.ACCIDENT: CardType.REPAIRS,
}
_SAFETY_FOR_ATTACK = {
    CardType.RED_LIGHT: CardType.PRIORITY_VEHICLE,
    CardType.SPEED_LIMIT: CardType.PRIORITY_VEHICLE,
    CardType.OUT_OF_FUEL: CardType.EXTRA_TANK,
    CardType.FLAT_TIRE: CardType.PUNCTURE_PROOF,
    CardType.ACCIDENT: CardType.DRIVING_ACE,
}
_ATTACKS_FOR_SAFETY = {
    CardType.PRIORITY_VEHICLE: frozenset(
        {CardType.RED_LIGHT, CardType.SPEED_LIMIT}
    ),
    CardType.EXTRA_TANK: frozenset({CardType.OUT_OF_FUEL}),
    CardType.PUNCTURE_PROOF: frozenset({CardType.FLAT_TIRE}),
    CardType.DRIVING_ACE: frozenset({CardType.ACCIDENT}),
}


class Strategy(Protocol):
    def choose(
        self,
        observation: GameObservation,
        legal_plays: Sequence[LegalPlay],
        rng: random.Random,
    ) -> AIAction: ...


def _card_lookup(observation: GameObservation) -> dict[str, Card]:
    return {card.id: card for card in observation.hand}


def _play_actions(
    observation: GameObservation,
    legal_plays: Sequence[LegalPlay],
) -> list[AIAction]:
    hand = _card_lookup(observation)
    return [
        AIAction(
            ActionType.PLAY,
            card_id=play.card_id,
            target_player_id=play.target_player_id,
        )
        for play in legal_plays
        if play.card_id in hand
        and (
            observation.phase != GamePhase.RESPONSE
            or play.is_coup_fourre
        )
    ]


def _discard_actions(observation: GameObservation) -> list[AIAction]:
    return [
        AIAction(ActionType.DISCARD, card_id=card.id)
        for card in observation.hand
    ]


def _available_actions(
    observation: GameObservation,
    legal_plays: Sequence[LegalPlay],
) -> list[AIAction]:
    plays = _play_actions(observation, legal_plays)
    if observation.phase == GamePhase.RESPONSE:
        return [*plays, AIAction(ActionType.PASS)]

    if observation.phase == GamePhase.ACTION:
        if observation.allow_voluntary_discard:
            return [*plays, *_discard_actions(observation)]
        if not plays:
            return _discard_actions(observation)
        return plays
    return []


def _choose_random(actions: Sequence[AIAction], rng: random.Random) -> AIAction:
    if not actions:
        raise ValueError("Aucune action candidate n’est disponible pour l’IA.")
    return rng.choice(list(actions))


def _best(
    scored_actions: Sequence[tuple[float, AIAction]],
    rng: random.Random,
) -> AIAction:
    if not scored_actions:
        raise ValueError("Aucune action candidate n’est disponible pour l’IA.")
    best_score = max(score for score, _ in scored_actions)
    ties = [action for score, action in scored_actions if score == best_score]
    return _choose_random(ties, rng)


def _distance_score(observation: GameObservation, card: Card) -> float:
    distance = card.distance_km or 0
    after_play = observation.player.distance + distance
    remaining = observation.target_distance - observation.player.distance
    score = 42 + distance * 0.17
    score += 12 * after_play / observation.target_distance
    if after_play == observation.target_distance:
        score += 500  # End the race whenever the engine says this is legal.
    elif remaining <= 200:
        score += 12
    elif remaining <= 400:
        score += 5
    if any(other.distance > observation.player.distance for other in observation.opponents):
        score += 4
    return score


def _repair_score(observation: GameObservation, card: Card) -> float:
    attack = observation.player.battle_attack
    if card.card_type == CardType.GREEN_LIGHT and observation.player.must_play_green_light:
        return 130
    if attack is not None and _PARADE_FOR_ATTACK.get(attack) == card.card_type:
        return 105 if attack == CardType.RED_LIGHT else 100
    if card.card_type == CardType.END_SPEED_LIMIT:
        return 88
    return 55


def _safety_score(observation: GameObservation, card: Card) -> float:
    covered = _ATTACKS_FOR_SAFETY.get(card.card_type, frozenset())
    threatened = observation.player.battle_attack in covered or (
        observation.player.speed_attack in covered
    )
    # A safety also grants a replay and a replacement draw in this ruleset.
    return 88 if threatened else 72


def _attack_score(
    observation: GameObservation,
    action: AIAction,
    card: Card,
) -> float:
    target = observation.opponent(action.target_player_id or "")
    if target is None:
        return -1000
    progress = target.distance / observation.target_distance
    lead = target.distance - observation.player.distance
    if card.card_type == CardType.SPEED_LIMIT:
        score = 39 + progress * 18
    else:
        score = 55 + progress * 25
    if lead > 0:
        score += min(18, 5 + lead / 35)
    return score


def _retention_value(observation: GameObservation, card: Card) -> float:
    """How costly it is to discard a card which cannot currently be played."""
    if card.category == CardCategory.DISTANCE:
        value = 35 + (card.distance_km or 0) * 0.20
        if card.card_type == CardType.KM_200:
            value += 8
        return value
    if card.category == CardCategory.SAFETY:
        return 80
    if card.category == CardCategory.ATTACK:
        return 43 if card.card_type == CardType.SPEED_LIMIT else 48
    if card.card_type == CardType.END_SPEED_LIMIT:
        return 52
    return 58


class EasyStrategy:
    """Makes a seeded random choice from engine-legal options."""

    def choose(self, observation, legal_plays, rng) -> AIAction:
        actions = _available_actions(observation, legal_plays)
        if observation.phase == GamePhase.DRAW:
            return AIAction(ActionType.DRAW)
        return _choose_random(actions, rng)


class NormalStrategy:
    """Favors progress, repairs and useful attacks while preserving good cards."""

    def choose(self, observation, legal_plays, rng) -> AIAction:
        if observation.phase == GamePhase.DRAW:
            return AIAction(ActionType.DRAW)
        actions = _available_actions(observation, legal_plays)
        cards = _card_lookup(observation)
        scored: list[tuple[float, AIAction]] = []
        for action in actions:
            card = cards.get(action.card_id or "")
            if action.action == ActionType.PASS:
                score = 5
            elif action.action == ActionType.DISCARD and card is not None:
                score = -_retention_value(observation, card)
            elif card is None:
                score = -1000
            elif card.category == CardCategory.DISTANCE:
                score = _distance_score(observation, card)
            elif card.category == CardCategory.PARADE:
                score = _repair_score(observation, card)
            elif card.category == CardCategory.SAFETY:
                score = _safety_score(observation, card)
            else:
                score = _attack_score(observation, action, card)
            scored.append((score, action))
        return _best(scored, rng)


class HardStrategy(NormalStrategy):
    """Uses endgame urgency and public-card probabilities to assess risk."""

    def choose(self, observation, legal_plays, rng) -> AIAction:
        if observation.phase == GamePhase.DRAW:
            return AIAction(ActionType.DRAW)
        actions = _available_actions(observation, legal_plays)
        cards = _card_lookup(observation)
        scored: list[tuple[float, AIAction]] = []
        for action in actions:
            card = cards.get(action.card_id or "")
            if action.action == ActionType.PASS:
                # A matching safety gets both protection and an immediate replay.
                score = 5
            elif action.action == ActionType.DISCARD and card is not None:
                score = -1.25 * _retention_value(observation, card)
            elif card is None:
                score = -1000
            elif card.category == CardCategory.DISTANCE:
                score = _distance_score(observation, card) + self._race_adjustment(
                    observation, card
                )
            elif card.category == CardCategory.PARADE:
                score = _repair_score(observation, card) + self._race_pressure(
                    observation
                )
            elif card.category == CardCategory.SAFETY:
                score = _safety_score(observation, card) + 8
            else:
                score = _attack_score(observation, action, card)
                score -= self._counterattack_risk(
                    observation, action, card.card_type
                )
                score += self._race_pressure(observation)
            scored.append((score, action))
        return _best(scored, rng)

    @staticmethod
    def _race_pressure(observation: GameObservation) -> float:
        leader = max(
            (other.distance for other in observation.opponents),
            default=observation.player.distance,
        )
        gap = leader - observation.player.distance
        return min(15, max(-8, gap / 30))

    @staticmethod
    def _race_adjustment(observation: GameObservation, card: Card) -> float:
        remaining = observation.target_distance - observation.player.distance
        after = observation.player.distance + (card.distance_km or 0)
        if after == observation.target_distance:
            return 1000
        if remaining <= 100:
            return (card.distance_km or 0) * 0.25
        return HardStrategy._race_pressure(observation) * 0.35

    @staticmethod
    def _counterattack_risk(
        observation: GameObservation,
        action: AIAction,
        attack_type: CardType,
    ) -> float:
        safety = _SAFETY_FOR_ATTACK.get(attack_type)
        target = observation.opponent(action.target_player_id or "")
        if safety is None or target is None or safety in target.safeties:
            return 0

        unseen_copies = observation.unseen_count(safety)
        unknown_locations = observation.draw_pile_count + sum(
            opponent.hand_size for opponent in observation.opponents
        )
        if unseen_copies <= 0 or unknown_locations <= 0:
            return 0
        # Only public hand sizes and unseen-card counts participate here. This
        # estimates, but never knows, whether the selected target holds a Botte.
        chance = min(1.0, unseen_copies * target.hand_size / unknown_locations)
        return chance * 72


_STRATEGIES: dict[Difficulty, Strategy] = {
    Difficulty.EASY: EasyStrategy(),
    Difficulty.NORMAL: NormalStrategy(),
    Difficulty.HARD: HardStrategy(),
}


def choose_action(
    observation: GameObservation,
    legal_plays: Sequence[LegalPlay],
    *,
    difficulty: Difficulty | str = Difficulty.NORMAL,
    rng: random.Random | None = None,
) -> AIAction:
    """Choose a command from sanitized information and engine legal-play hints.

    The returned command is still submitted to ``apply_action``; that engine
    validation is authoritative even though the strategy only selects legal
    candidates.
    """
    if not observation.is_actor:
        raise ValueError("L’IA ne peut choisir que lorsque le joueur doit agir.")
    if observation.phase == GamePhase.FINISHED:
        raise ValueError("La partie est terminée.")
    try:
        selected_difficulty = Difficulty(difficulty)
    except ValueError as exc:
        raise ValueError(f"Difficulté d’IA inconnue : {difficulty!r}.") from exc

    return _STRATEGIES[selected_difficulty].choose(
        observation,
        legal_plays,
        rng or random.Random(),
    )
