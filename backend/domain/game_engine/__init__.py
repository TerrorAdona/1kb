"""Pure Python Mille Bornes rules engine.

The engine is the authority for legality. Callers should send commands (player,
action and card IDs), never a client-computed state.
"""

from .cards import CARD_CATALOG, Card, CardCategory, CardType, build_deck
from .engine import (
    ActionType,
    EngineEvent,
    LegalPlay,
    RuleViolation,
    Transition,
    apply_action,
    calculate_scores,
    legal_plays,
    new_game,
    score_player,
)
from .models import (
    GamePhase,
    GameState,
    PlayerState,
    RULESET_VERSION,
    RulesConfig,
    state_from_dict,
    state_to_dict,
)

__all__ = [
    "CARD_CATALOG",
    "ActionType",
    "Card",
    "CardCategory",
    "CardType",
    "EngineEvent",
    "GamePhase",
    "GameState",
    "LegalPlay",
    "PlayerState",
    "RULESET_VERSION",
    "RuleViolation",
    "RulesConfig",
    "Transition",
    "apply_action",
    "build_deck",
    "calculate_scores",
    "legal_plays",
    "new_game",
    "score_player",
    "state_from_dict",
    "state_to_dict",
]
