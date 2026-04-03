from __future__ import annotations

from canasta.model import WILD_RANKS, Card, Meld

CARD_POINTS = {
    "JOKER": 50,
    "2": 20,
    "A": 20,
    "K": 10,
    "Q": 10,
    "J": 10,
    "T": 10,
    "9": 10,
    "8": 10,
    "7": 5,
    "6": 5,
    "5": 5,
    "4": 5,
    "3": 5,
}


def validate_meld_cards(cards: list[Card]) -> tuple[bool, str]:
    if len(cards) < 3:
        return False, "meld requires at least 3 cards"

    naturals = [card for card in cards if card.rank not in WILD_RANKS]
    wilds = [card for card in cards if card.rank in WILD_RANKS]

    if not naturals:
        return False, "meld cannot be all wild cards"

    natural_rank = naturals[0].rank
    if any(card.rank != natural_rank for card in naturals):
        return False, "natural cards in meld must have same rank"

    if len(wilds) > len(naturals):
        return False, "wild cards cannot outnumber natural cards"

    return True, "ok"


def can_add_cards_to_meld(meld: Meld, cards: list[Card]) -> tuple[bool, str]:
    candidate = meld.cards + cards
    return validate_meld_cards(candidate)


def can_discard(card: Card) -> tuple[bool, str]:
    if card.rank == "3" and card.suit in {"H", "D"}:
        return False, "red threes cannot be discarded"
    return True, "ok"


def hand_score(cards: list[Card]) -> int:
    return sum(CARD_POINTS[card.rank] for card in cards)


def meld_score(melds: list[Meld]) -> int:
    total = 0
    for meld in melds:
        total += hand_score(meld.cards)
        if len(meld.cards) >= 7:
            total += 300
    return total
