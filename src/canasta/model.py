from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K")
SUITS = ("S", "H", "D", "C")
WILD_RANKS = {"2", "JOKER"}
DRAW_COUNT_PER_TURN = 2


class PlayerId(str, Enum):
    NORTH = "north"
    SOUTH = "south"


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str | None = None

    def label(self) -> str:
        if self.rank == "JOKER":
            return "JOKER"
        return f"{self.rank}{self.suit}"

    def is_wild(self) -> bool:
        return self.rank in WILD_RANKS

    def is_red_three(self) -> bool:
        return self.rank == "3" and self.suit in {"H", "D"}


@dataclass
class Meld:
    cards: list[Card]

    @property
    def natural_rank(self) -> str:
        for card in self.cards:
            if not card.is_wild():
                return card.rank
        return ""

    @property
    def natural_count(self) -> int:
        return sum(1 for card in self.cards if not card.is_wild())

    @property
    def wild_count(self) -> int:
        return sum(1 for card in self.cards if card.is_wild())

    @property
    def is_canasta(self) -> bool:
        return len(self.cards) >= 7


@dataclass
class PlayerState:
    hand: list[Card] = field(default_factory=list)
    melds: list[Meld] = field(default_factory=list)
    red_threes: list[Card] = field(default_factory=list)
    score: int = 0


@dataclass
class GameState:
    players: dict[PlayerId, PlayerState]
    current_player: PlayerId
    stock: list[Card]
    discard: list[Card]
    turn_drawn: bool = False
    winner: PlayerId | None = None


def build_double_deck() -> list[Card]:
    deck: list[Card] = []
    for _ in range(2):
        for suit in SUITS:
            for rank in RANKS:
                deck.append(Card(rank=rank, suit=suit))
        deck.append(Card(rank="JOKER"))
        deck.append(Card(rank="JOKER"))
    return deck


def hand_labels(hand: Iterable[Card]) -> list[str]:
    return [card.label() for card in hand]
