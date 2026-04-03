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


OPENING_MELD_MINIMUM = 50


def is_discard_freeze_card(card: Card) -> bool:
    return card.is_wild() or card.is_black_three()


def discard_pile_is_frozen(discard: list[Card]) -> bool:
    return any(is_discard_freeze_card(card) for card in discard)


def can_pickup_frozen_discard(top_discard: Card, cards: list[Card]) -> tuple[bool, str]:
    if top_discard.is_wild() or top_discard.is_black_three():
        return (
            False,
            "cannot pick up a frozen pile with a wild card or black three on top",
        )
    if len(cards) != 2:
        return False, "frozen discard pickup requires exactly 2 hand cards"
    if any(card.is_wild() for card in cards):
        return False, "frozen discard pickup requires natural matching cards"
    if any(card.rank != top_discard.rank for card in cards):
        return (
            False,
            "frozen discard pickup requires a natural pair matching the top discard",
        )
    return True, "ok"


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


def split_meld_cards(
    cards: list[Card], *, allow_multi_rank: bool = False
) -> tuple[list[list[Card]] | None, str]:
    ok, reason = validate_meld_cards(cards)
    if ok:
        return [cards], "ok"

    if not allow_multi_rank:
        return None, reason

    naturals = [card for card in cards if card.rank not in WILD_RANKS]
    wilds = [card for card in cards if card.rank in WILD_RANKS]
    if not naturals:
        return None, "meld cannot be all wild cards"
    if wilds:
        return None, "split-rank melds cannot include wild cards in one action"

    groups: dict[str, list[Card]] = {}
    for card in cards:
        groups.setdefault(card.rank, []).append(card)

    if len(groups) < 2:
        return None, reason
    if any(len(group) < 3 for group in groups.values()):
        return None, "each rank in a split meld must contain at least 3 cards"

    return list(groups.values()), "ok"


def can_add_cards_to_meld(meld: Meld, cards: list[Card]) -> tuple[bool, str]:
    candidate = meld.cards + cards
    return validate_meld_cards(candidate)


def validate_pickup_cards(
    top_discard: Card,
    hand_cards: list[Card],
    *,
    allow_multi_rank: bool = False,
) -> tuple[list[list[Card]] | None, str]:
    """Validate hand cards + top discard for a pickup action.

    Returns a list of meld card groups (the group containing top_discard is
    first) or (None, reason) on failure.  When allow_multi_rank is True (used
    for the opening meld), selected hand cards may span multiple natural ranks
    provided each rank forms its own valid meld of ≥3 cards — no wild cards
    are permitted in a split pickup.
    """
    all_cards = hand_cards + [top_discard]

    # Always try single-rank first (existing behaviour, also covers wild melds).
    ok, reason = validate_meld_cards(all_cards)
    if ok:
        return [all_cards], "ok"

    if not allow_multi_rank:
        return None, reason

    # Multi-rank split: wild cards cannot be distributed unambiguously.
    if any(card.is_wild() for card in all_cards):
        return None, "split-rank pickup melds cannot include wild cards"

    groups: dict[str, list[Card]] = {}
    for card in all_cards:
        groups.setdefault(card.rank, []).append(card)

    if len(groups) < 2:
        return None, reason  # single rank but still failed above

    for rank, group in groups.items():
        if len(group) < 3:
            return None, (
                f"each rank in a split pickup must have at least 3 cards "
                f"(rank {rank} has {len(group)})"
            )

    discard_rank = top_discard.rank
    result = [groups[discard_rank]] + [
        g for r, g in groups.items() if r != discard_rank
    ]
    return result, "ok"


def can_discard(card: Card) -> tuple[bool, str]:
    if card.rank == "3" and card.suit in {"H", "D"}:
        return False, "red threes cannot be discarded"
    return True, "ok"


def red_three_score(red_threes: list[Card]) -> int:
    """100 pts each; all four doubles to 200 each (800 total)."""
    count = len(red_threes)
    if count == 0:
        return 0
    per_card = 200 if count == 4 else 100
    return count * per_card


def opening_meld_value(cards: list[Card]) -> int:
    """Point value of natural cards only — used to check the opening meld minimum.

    Wild cards do not count towards the opening threshold.
    """
    return sum(CARD_POINTS[card.rank] for card in cards if card.rank not in WILD_RANKS)


def hand_penalty(cards: list[Card]) -> int:
    """Round-end penalty for cards left in hand.

    This currently uses the same point table as positive card scoring.
    """
    return hand_score(cards)


def hand_score(cards: list[Card]) -> int:
    return sum(CARD_POINTS[card.rank] for card in cards)


def meld_score(melds: list[Meld]) -> int:
    total = 0
    for meld in melds:
        total += hand_score(meld.cards)
        if len(meld.cards) >= 7:
            total += 300
    return total
