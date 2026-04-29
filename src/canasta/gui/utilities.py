"""Card and meld utility functions for the GUI."""

from __future__ import annotations

from collections import Counter

from canasta.model import Card, Meld, RuleError


def format_card(card: Card) -> str:
    """Format a card for display."""
    if card.rank == "JOKER":
        return "JOKER"
    return f"{card.rank}{card.suit}"


def resolve_target_meld_index(melds: list[Meld], cards: list[Card]) -> int | None:
    """Determine which meld to add cards to, or None if ambiguous/invalid.

    Raises RuleError if cards cannot be added to any meld.
    """
    if not cards:
        raise RuleError("select cards to add")
    if any(card.is_wild() for card in cards):
        return None

    natural_ranks = {card.rank for card in cards}
    if len(natural_ranks) != 1:
        raise RuleError("selected cards must all match one meld rank")

    target_rank = natural_ranks.pop()
    matching_indexes = [
        idx for idx, meld in enumerate(melds) if meld.natural_rank == target_rank
    ]
    if not matching_indexes:
        raise RuleError(f"no existing meld for rank {target_rank}")
    if len(matching_indexes) > 1:
        raise RuleError(f"multiple melds found for rank {target_rank}")
    return matching_indexes[0]


def card_key(card: Card) -> tuple[str, str | None]:
    """Return a sortable key for a card (rank, suit)."""
    return (card.rank, card.suit)


def new_cards_in_hand(before: list[Card], after: list[Card]) -> list[Card]:
    """Return net-added cards between two hand snapshots."""
    before_counts = Counter(card_key(card) for card in before)
    added: list[Card] = []
    for card in after:
        key = card_key(card)
        if before_counts[key] > 0:
            before_counts[key] -= 1
            continue
        added.append(card)
    return added


def reorganize_meld_cards(cards: list[Card]) -> list[Card]:
    """Reorder meld cards: natural cards first, wild cards last."""
    natural = [card for card in cards if not card.is_wild()]
    wild = [card for card in cards if card.is_wild()]
    return natural + wild


def rank_sort_key(rank: str) -> tuple[int, str]:
    """Return sort key for a rank to sort melds numerically.

    Sorts by index in RANKS tuple (A, 2, 3, ..., K), with non-matching ranks last.
    """
    RANKS_TUPLE = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K")
    try:
        return (RANKS_TUPLE.index(rank), rank)
    except ValueError:
        return (len(RANKS_TUPLE), rank)
