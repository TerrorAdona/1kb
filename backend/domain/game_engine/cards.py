"""Card definitions and the Dujardin Classique 2025 playable deck."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable
from uuid import uuid4


class CardCategory(str, Enum):
    DISTANCE = "distance"
    ATTACK = "attack"
    PARADE = "parade"
    SAFETY = "safety"


class CardType(str, Enum):
    KM_25 = "km_25"
    KM_50 = "km_50"
    KM_75 = "km_75"
    KM_100 = "km_100"
    KM_200 = "km_200"

    SPEED_LIMIT = "speed_limit"
    RED_LIGHT = "red_light"
    OUT_OF_FUEL = "out_of_fuel"
    FLAT_TIRE = "flat_tire"
    ACCIDENT = "accident"

    GREEN_LIGHT = "green_light"
    END_SPEED_LIMIT = "end_speed_limit"
    FUEL = "fuel"
    SPARE_TIRE = "spare_tire"
    REPAIRS = "repairs"

    PRIORITY_VEHICLE = "priority_vehicle"
    EXTRA_TANK = "extra_tank"
    PUNCTURE_PROOF = "puncture_proof"
    DRIVING_ACE = "driving_ace"


@dataclass(frozen=True, slots=True)
class CardDefinition:
    category: CardCategory
    quantity: int
    distance_km: int | None = None


CARD_CATALOG: dict[CardType, CardDefinition] = {
    CardType.KM_25: CardDefinition(CardCategory.DISTANCE, 10, 25),
    CardType.KM_50: CardDefinition(CardCategory.DISTANCE, 10, 50),
    CardType.KM_75: CardDefinition(CardCategory.DISTANCE, 10, 75),
    CardType.KM_100: CardDefinition(CardCategory.DISTANCE, 12, 100),
    CardType.KM_200: CardDefinition(CardCategory.DISTANCE, 4, 200),
    CardType.SPEED_LIMIT: CardDefinition(CardCategory.ATTACK, 4),
    CardType.RED_LIGHT: CardDefinition(CardCategory.ATTACK, 5),
    CardType.OUT_OF_FUEL: CardDefinition(CardCategory.ATTACK, 3),
    CardType.FLAT_TIRE: CardDefinition(CardCategory.ATTACK, 3),
    CardType.ACCIDENT: CardDefinition(CardCategory.ATTACK, 3),
    CardType.GREEN_LIGHT: CardDefinition(CardCategory.PARADE, 14),
    CardType.END_SPEED_LIMIT: CardDefinition(CardCategory.PARADE, 6),
    CardType.FUEL: CardDefinition(CardCategory.PARADE, 6),
    CardType.SPARE_TIRE: CardDefinition(CardCategory.PARADE, 6),
    CardType.REPAIRS: CardDefinition(CardCategory.PARADE, 6),
    CardType.PRIORITY_VEHICLE: CardDefinition(CardCategory.SAFETY, 1),
    CardType.EXTRA_TANK: CardDefinition(CardCategory.SAFETY, 1),
    CardType.PUNCTURE_PROOF: CardDefinition(CardCategory.SAFETY, 1),
    CardType.DRIVING_ACE: CardDefinition(CardCategory.SAFETY, 1),
}


@dataclass(frozen=True, slots=True)
class Card:
    id: str
    card_type: CardType

    @property
    def category(self) -> CardCategory:
        return CARD_CATALOG[self.card_type].category

    @property
    def distance_km(self) -> int | None:
        return CARD_CATALOG[self.card_type].distance_km

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "card_type": self.card_type.value}

    @classmethod
    def from_dict(cls, value: dict[str, str]) -> Card:
        return cls(id=str(value["id"]), card_type=CardType(value["card_type"]))


def build_deck(
    *,
    id_factory: Callable[[], str] | None = None,
) -> list[Card]:
    """Build the 106 playable cards (the four memo cards are not playable)."""
    make_id = id_factory or (lambda: str(uuid4()))
    return [
        Card(id=make_id(), card_type=card_type)
        for card_type, definition in CARD_CATALOG.items()
        for _ in range(definition.quantity)
    ]
