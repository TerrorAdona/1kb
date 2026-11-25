"""Public-only observations and configuration for the game AI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from domain.game_engine import ActionType, Card, CardType, GamePhase


class Difficulty(str, Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"


@dataclass(frozen=True, slots=True)
class AIConfig:
    """Per-bot settings. A seed makes all tie-breaking reproducible."""

    difficulty: Difficulty = Difficulty.NORMAL
    thinking_delay_seconds: float = 0.6
    seed: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "difficulty", Difficulty(self.difficulty))
        if not isfinite(self.thinking_delay_seconds) or self.thinking_delay_seconds < 0:
            raise ValueError("Le délai doit être un nombre fini positif ou nul.")


@dataclass(frozen=True, slots=True)
class AIAction:
    """An engine command chosen by a strategy, never a state mutation."""

    action: ActionType
    card_id: str | None = None
    target_player_id: str | None = None

    def to_engine_kwargs(self) -> dict[str, str | None]:
        return {
            "action": self.action.value,
            "card_id": self.card_id,
            "target_player_id": self.target_player_id,
        }


@dataclass(frozen=True, slots=True)
class PlayerObservation:
    """A player's public board plus public hand size (never its hand)."""

    player_id: str
    hand_size: int
    distance: int
    battle_attack: CardType | None
    speed_attack: CardType | None
    green_light_active: bool
    must_play_green_light: bool
    safeties: frozenset[CardType]
    count_200_cards: int

    @property
    def has_rolled(self) -> bool:
        return self.distance > 0


@dataclass(frozen=True, slots=True)
class GameObservation:
    """An AI's view of a game, intentionally excluding hidden card identities.

    ``hand`` belongs only to ``player_id``. Opponents are represented by their
    public board and hand sizes. The draw pile is represented by its size only.
    ``unseen_card_counts`` is a probability aid computed from the catalog,
    public cards and the AI's own hand; it never reports where a card is.
    """

    player_id: str
    phase: GamePhase
    active_player_id: str
    pending_response_player_id: str | None
    pending_response_attack: CardType | None
    player: PlayerObservation
    hand: tuple[Card, ...]
    opponents: tuple[PlayerObservation, ...]
    draw_pile_count: int
    discard_pile: tuple[CardType, ...]
    unseen_card_counts: tuple[tuple[CardType, int], ...]
    target_distance: int
    speed_limit_max: int
    max_200_cards: int
    allow_voluntary_discard: bool

    @property
    def is_actor(self) -> bool:
        if self.phase in (GamePhase.DRAW, GamePhase.ACTION):
            return self.active_player_id == self.player_id
        if self.phase == GamePhase.RESPONSE:
            return self.pending_response_player_id == self.player_id
        return False

    def unseen_count(self, card_type: CardType) -> int:
        return next(
            (count for known_type, count in self.unseen_card_counts
             if known_type == card_type),
            0,
        )

    def opponent(self, player_id: str) -> PlayerObservation | None:
        return next(
            (player for player in self.opponents if player.player_id == player_id),
            None,
        )
