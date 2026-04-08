"""Hand utilities for card manipulation."""

from canasta.model import SUITS, Card, RuleError
from canasta.rules import CARD_POINTS


def pop_cards_from_hand(hand: list[Card], indexes: list[int]) -> list[Card]:
    """Remove and return cards from hand by their indexes.

    Args:
        hand: The player's hand list (modified in-place).
        indexes: List of indexes to remove.

    Returns:
        List of removed cards in original order.

    Raises:
        RuleError: If indexes are invalid, duplicate, or out of range.
    """
    if not indexes:
        raise RuleError("no card indexes provided")
    unique_indexes = sorted(set(indexes), reverse=True)
    if len(unique_indexes) != len(indexes):
        raise RuleError("duplicate card indexes")
    cards: list[Card] = []
    for idx in unique_indexes:
        if idx < 0 or idx >= len(hand):
            raise RuleError("invalid hand index")
        cards.append(hand.pop(idx))
    cards.reverse()
    return cards


def sort_hand(hand: list[Card]) -> None:
    """Sort hand by score then natural rank order for consistent display.

    Primary: ascending card point value (threes/low cards on left, wilds on right).
    Secondary: natural rank order (3–K, A, 2, JOKER) within the same score tier.
    Tertiary: suit order (S-C) for identical rank.

    Args:
        hand: The player's hand list (sorted in-place).
    """
    # Natural rank order: 3 4 5 6 7 8 9 T J Q K A 2 JOKER
    natural_rank_order = {
        rank: idx
        for idx, rank in enumerate(
            ("3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A", "2", "JOKER")
        )
    }
    suit_order = {suit: idx for idx, suit in enumerate(SUITS)}
    suit_order[None] = len(SUITS)

    hand.sort(
        key=lambda card: (
            CARD_POINTS.get(card.rank, 0),
            natural_rank_order.get(card.rank, len(natural_rank_order)),
            suit_order.get(card.suit, len(SUITS) + 1),
        )
    )
