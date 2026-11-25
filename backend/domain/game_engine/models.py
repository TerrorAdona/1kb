"""Serializable state and configurable rules for a Mille Bornes game."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .cards import Card, CardType


RULESET_VERSION = "mille-bornes-v1"


class GamePhase(str, Enum):
    DRAW = "draw"
    ACTION = "action"
    RESPONSE = "response"
    FINISHED = "finished"


@dataclass(frozen=True, slots=True)
class RulesConfig:
    """Ruleset options; defaults match Dujardin Classique 2025, ref. 1130300292."""

    ruleset_version: str = RULESET_VERSION
    target_distance: int = 1000
    max_players: int = 4
    initial_hand_size: int = 6
    speed_limit_max: int = 50
    max_200_cards: int = 2
    start_requires_green_light: bool = False
    require_green_after_repair: bool = False
    end_when_no_distance_cards: bool = True
    allow_voluntary_discard: bool = False

    def __post_init__(self) -> None:
        if not self.ruleset_version:
            raise ValueError("ruleset_version ne peut pas être vide.")
        if self.target_distance <= 0:
            raise ValueError("target_distance doit être positif.")
        if not 2 <= self.max_players <= 4:
            raise ValueError("max_players doit être compris entre 2 et 4.")
        if self.initial_hand_size <= 0:
            raise ValueError("initial_hand_size doit être positif.")
        if self.speed_limit_max < 0:
            raise ValueError("speed_limit_max ne peut pas être négatif.")
        if self.max_200_cards < 0:
            raise ValueError("max_200_cards ne peut pas être négatif.")

    def to_dict(self) -> dict[str, object]:
        return {
            "ruleset_version": self.ruleset_version,
            "target_distance": self.target_distance,
            "max_players": self.max_players,
            "initial_hand_size": self.initial_hand_size,
            "speed_limit_max": self.speed_limit_max,
            "max_200_cards": self.max_200_cards,
            "start_requires_green_light": self.start_requires_green_light,
            "require_green_after_repair": self.require_green_after_repair,
            "end_when_no_distance_cards": self.end_when_no_distance_cards,
            "allow_voluntary_discard": self.allow_voluntary_discard,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> RulesConfig:
        return cls(**value)


@dataclass(slots=True)
class PlayerState:
    player_id: str
    hand: list[Card] = field(default_factory=list)
    distance_cards: list[Card] = field(default_factory=list)
    battle_attack: Card | None = None
    speed_attack: Card | None = None
    green_light_card: Card | None = None
    safeties: set[CardType] = field(default_factory=set)
    must_play_green_light: bool = False
    coup_fourres: int = 0

    @property
    def distance(self) -> int:
        return sum(card.distance_km or 0 for card in self.distance_cards)

    @property
    def count_200_cards(self) -> int:
        return sum(card.card_type == CardType.KM_200 for card in self.distance_cards)

    @property
    def has_rolled(self) -> bool:
        return self.distance > 0

    @property
    def is_speed_limited(self) -> bool:
        return self.speed_attack is not None

    @property
    def has_green_light(self) -> bool:
        return self.green_light_card is not None


@dataclass(slots=True)
class GameState:
    players: list[PlayerState]
    draw_pile: list[Card]
    discard_pile: list[Card]
    active_player_index: int
    phase: GamePhase
    rules: RulesConfig
    turn_number: int = 1
    pending_response_player_id: str | None = None
    pending_response_attack: Card | None = None
    winner_ids: list[str] = field(default_factory=list)
    finish_reason: str | None = None

    @property
    def active_player(self) -> PlayerState:
        return self.players[self.active_player_index]

    @property
    def winner_id(self) -> str | None:
        return self.winner_ids[0] if len(self.winner_ids) == 1 else None


def state_to_dict(state: GameState) -> dict[str, object]:
    """Return a JSON-compatible server snapshot suitable for a JSONField."""
    return {
        "players": [
            {
                "player_id": player.player_id,
                "hand": [card.to_dict() for card in player.hand],
                "distance_cards": [card.to_dict() for card in player.distance_cards],
                "battle_attack": (
                    player.battle_attack.to_dict() if player.battle_attack else None
                ),
                "speed_attack": (
                    player.speed_attack.to_dict() if player.speed_attack else None
                ),
                "green_light_card": (
                    player.green_light_card.to_dict()
                    if player.green_light_card
                    else None
                ),
                "safeties": sorted(card_type.value for card_type in player.safeties),
                "must_play_green_light": player.must_play_green_light,
                "coup_fourres": player.coup_fourres,
            }
            for player in state.players
        ],
        "draw_pile": [card.to_dict() for card in state.draw_pile],
        "discard_pile": [card.to_dict() for card in state.discard_pile],
        "active_player_index": state.active_player_index,
        "phase": state.phase.value,
        "rules": state.rules.to_dict(),
        "turn_number": state.turn_number,
        "pending_response_player_id": state.pending_response_player_id,
        "pending_response_attack": (
            state.pending_response_attack.to_dict()
            if state.pending_response_attack
            else None
        ),
        "winner_ids": list(state.winner_ids),
        "finish_reason": state.finish_reason,
    }


def state_from_dict(value: dict[str, object]) -> GameState:
    """Restore a state snapshot previously produced by :func:`state_to_dict`."""
    players_value = value["players"]
    if not isinstance(players_value, list):
        raise ValueError("Le snapshot doit contenir une liste de joueurs.")

    players: list[PlayerState] = []
    for raw in players_value:
        if not isinstance(raw, dict):
            raise ValueError("Entrée joueur invalide dans le snapshot.")
        players.append(
            PlayerState(
                player_id=str(raw["player_id"]),
                hand=[Card.from_dict(card) for card in raw["hand"]],
                distance_cards=[
                    Card.from_dict(card) for card in raw["distance_cards"]
                ],
                battle_attack=(
                    Card.from_dict(raw["battle_attack"])
                    if raw.get("battle_attack")
                    else None
                ),
                speed_attack=(
                    Card.from_dict(raw["speed_attack"])
                    if raw.get("speed_attack")
                    else None
                ),
                green_light_card=(
                    Card.from_dict(raw["green_light_card"])
                    if raw.get("green_light_card")
                    else None
                ),
                safeties={CardType(card_type) for card_type in raw["safeties"]},
                must_play_green_light=bool(raw["must_play_green_light"]),
                coup_fourres=int(raw["coup_fourres"]),
            )
        )

    rules_value = value["rules"]
    if not isinstance(rules_value, dict):
        raise ValueError("Configuration de règles invalide dans le snapshot.")
    draw_pile = value["draw_pile"]
    discard_pile = value["discard_pile"]
    if not isinstance(draw_pile, list) or not isinstance(discard_pile, list):
        raise ValueError("Les piles de cartes du snapshot doivent être des listes.")

    return GameState(
        players=players,
        draw_pile=[Card.from_dict(card) for card in draw_pile],
        discard_pile=[Card.from_dict(card) for card in discard_pile],
        active_player_index=int(value["active_player_index"]),
        phase=GamePhase(value["phase"]),
        rules=RulesConfig.from_dict(rules_value),
        turn_number=int(value["turn_number"]),
        pending_response_player_id=(
            str(value["pending_response_player_id"])
            if value.get("pending_response_player_id") is not None
            else None
        ),
        pending_response_attack=(
            Card.from_dict(value["pending_response_attack"])
            if value.get("pending_response_attack")
            else None
        ),
        winner_ids=[str(player_id) for player_id in value.get("winner_ids", [])],
        finish_reason=(
            str(value["finish_reason"])
            if value.get("finish_reason") is not None
            else None
        ),
    )
