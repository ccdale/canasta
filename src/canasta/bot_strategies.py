"""Bot strategy implementations for Canasta."""

import random
from dataclasses import dataclass
from typing import Protocol

from canasta.model import Card, RuleError
from canasta.rules import (
    OPENING_MELD_MINIMUM,
    can_discard,
    hand_score,
    opening_meld_value,
)


class TurnBot(Protocol):
    """Protocol for bot turn decision-making."""

    name: str

    def choose_meld_indexes(
        self, hand: list[Card], opening_required: bool
    ) -> list[int] | None: ...

    def choose_discard_index(self, hand: list[Card]) -> int: ...


@dataclass
class RandomBot:
    """Random bot: chooses Legal moves stochastically."""

    rng: random.Random
    name: str = "random"

    def choose_meld_indexes(
        self, hand: list[Card], opening_required: bool
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(hand, opening_required)
        if not candidates:
            return None
        return self.rng.choice(candidates)

    def choose_discard_index(self, hand: list[Card]) -> int:
        safe = [idx for idx, card in enumerate(hand) if can_discard(card)[0]]
        if not safe:
            raise RuleError("bot could not find a legal discard")
        return self.rng.choice(safe)


@dataclass
class GreedyBot:
    """Greedy bot: maximizes immediate card value and discard value."""

    name: str = "greedy"

    def choose_meld_indexes(
        self, hand: list[Card], opening_required: bool
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(hand, opening_required)
        if not candidates:
            return None
        # Maximize immediate card value to push opening and canasta progress.
        return max(
            candidates,
            key=lambda idxs: (hand_score([hand[i] for i in idxs]), len(idxs)),
        )

    def choose_discard_index(self, hand: list[Card]) -> int:
        safe = [idx for idx, card in enumerate(hand) if can_discard(card)[0]]
        if not safe:
            raise RuleError("bot could not find a legal discard")
        return min(safe, key=lambda idx: (hand_score([hand[idx]]), hand[idx].is_wild()))


@dataclass
class SafeBot:
    """Conservative bot: cautious melding and low-risk discard preferences."""

    name: str = "safe"

    def choose_meld_indexes(
        self, hand: list[Card], opening_required: bool
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(hand, opening_required)
        if not candidates:
            return None

        if not opening_required:
            # Hold cards for flexibility once the opening requirement is already met.
            return None

        # Open with the lowest-value legal candidate that satisfies threshold.
        return min(
            candidates,
            key=lambda idxs: (hand_score([hand[i] for i in idxs]), len(idxs)),
        )

    def choose_discard_index(self, hand: list[Card]) -> int:
        safe = [idx for idx, card in enumerate(hand) if can_discard(card)[0]]
        if not safe:
            raise RuleError("bot could not find a legal discard")

        rank_counts: dict[str, int] = {}
        for card in hand:
            rank_counts[card.rank] = rank_counts.get(card.rank, 0) + 1

        def discard_key(idx: int) -> tuple[int, int, int, int]:
            card = hand[idx]
            # Black threes are strong defensive discards because they freeze the pile.
            freeze_bonus = 0 if card.is_black_three() else 1
            singleton_bonus = 0 if rank_counts[card.rank] == 1 else 1
            wild_penalty = 1 if card.is_wild() else 0
            points = hand_score([card])
            return (freeze_bonus, wild_penalty, singleton_bonus, points)

        return min(safe, key=discard_key)


@dataclass
class AggroBot:
    """Aggressive bot: meld as much as possible, discard highest-risk points last."""

    name: str = "aggro"

    def choose_meld_indexes(
        self, hand: list[Card], opening_required: bool
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(hand, opening_required)
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda idxs: (len(idxs), hand_score([hand[i] for i in idxs])),
        )

    def choose_discard_index(self, hand: list[Card]) -> int:
        safe = [idx for idx, card in enumerate(hand) if can_discard(card)[0]]
        if not safe:
            raise RuleError("bot could not find a legal discard")
        # Dump highest points first; prefer non-wild when tied.
        return max(safe, key=lambda idx: (hand_score([hand[idx]]), hand[idx].is_wild()))


@dataclass
class PlannerBot:
    """Balanced bot: meld strong candidates, keep synergy, discard with medium risk."""

    name: str = "planner"

    def choose_meld_indexes(
        self, hand: list[Card], opening_required: bool
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(hand, opening_required)
        if not candidates:
            return None

        def meld_key(idxs: list[int]) -> tuple[int, int, int]:
            cards = [hand[i] for i in idxs]
            return (hand_score(cards), len(idxs), _natural_density(cards))

        return max(candidates, key=meld_key)

    def choose_discard_index(self, hand: list[Card]) -> int:
        safe = [idx for idx, card in enumerate(hand) if can_discard(card)[0]]
        if not safe:
            raise RuleError("bot could not find a legal discard")

        rank_counts: dict[str, int] = {}
        for card in hand:
            rank_counts[card.rank] = rank_counts.get(card.rank, 0) + 1

        def discard_key(idx: int) -> tuple[int, int, int, int]:
            card = hand[idx]
            # Keep wilds and keep pairs/triples for future melds when possible.
            wild_penalty = 1 if card.is_wild() else 0
            grouped_penalty = 1 if rank_counts[card.rank] > 1 else 0
            freeze_bonus = 0 if card.is_black_three() else 1
            points = hand_score([card])
            return (wild_penalty, grouped_penalty, freeze_bonus, points)

        return min(safe, key=discard_key)


def _eligible_natural_meld_candidates(
    hand: list[Card], opening_required: bool
) -> list[list[int]]:
    """Find all eligible natural card meld candidates in a hand.

    Args:
        hand: The player's hand.
        opening_required: Whether the opening meld minimum applies.

    Returns:
        List of index groups that form valid melds (3+ naturals of same rank).
    """
    by_rank: dict[str, list[int]] = {}
    for idx, card in enumerate(hand):
        if card.is_wild() or card.rank == "JOKER":
            continue
        by_rank.setdefault(card.rank, []).append(idx)

    candidates: list[list[int]] = []
    rank_candidates: list[list[list[int]]] = []
    for indexes in by_rank.values():
        if len(indexes) < 3:
            continue
        per_rank: list[list[int]] = []
        for size in range(3, len(indexes) + 1):
            candidate = indexes[:size]
            if not opening_required:
                candidates.append(candidate)
                continue

            points = opening_meld_value([hand[i] for i in candidate])
            if points >= OPENING_MELD_MINIMUM:
                candidates.append(candidate)
            per_rank.append(candidate)

        if opening_required and per_rank:
            rank_candidates.append(per_rank)

    if opening_required:
        # Opening meld may be split across multiple natural ranks in one action.
        split_candidates = _opening_split_candidates(hand, rank_candidates)
        candidates.extend(split_candidates)

    return candidates


def _opening_split_candidates(
    hand: list[Card], rank_candidates: list[list[list[int]]]
) -> list[list[int]]:
    """Build opening meld candidates that combine multiple natural ranks."""
    if len(rank_candidates) < 2:
        return []

    results: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()

    def add_candidate(indexes: list[int]) -> None:
        if len(indexes) < 6:
            return
        points = opening_meld_value([hand[i] for i in indexes])
        if points < OPENING_MELD_MINIMUM:
            return
        key = tuple(sorted(indexes))
        if key in seen:
            return
        seen.add(key)
        results.append(indexes)

    def walk(rank_idx: int, selected: list[list[int]]) -> None:
        if rank_idx == len(rank_candidates):
            if len(selected) < 2:
                return
            merged: list[int] = []
            for group in selected:
                merged.extend(group)
            add_candidate(merged)
            return

        # Skip this rank.
        walk(rank_idx + 1, selected)

        # Include one candidate size from this rank.
        for candidate in rank_candidates[rank_idx]:
            selected.append(candidate)
            walk(rank_idx + 1, selected)
            selected.pop()

    walk(0, [])
    return results


def _natural_density(cards: list[Card]) -> int:
    """Count natural cards in a list."""
    return sum(1 for card in cards if not card.is_wild())
