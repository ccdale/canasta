"""Hand utilities for card manipulation."""

from canasta.model import RANKS, SUITS, Card, RuleError


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
    """Sort hand by rank then suit for consistent display.

    Sorts in-place using RANKS order (A-K) and SUITS order (S-C),
    with JOKER and None (wild 2) sorted last.

    Args:
        hand: The player's hand list (sorted in-place).
    """
    rank_order = {rank: idx for idx, rank in enumerate(RANKS)}
    rank_order["JOKER"] = len(RANKS)
    suit_order = {suit: idx for idx, suit in enumerate(SUITS)}
    suit_order[None] = len(SUITS)

    hand.sort(
        key=lambda card: (
            rank_order.get(card.rank, len(RANKS) + 1),
            suit_order.get(card.suit, len(SUITS) + 1),
        )
    )
