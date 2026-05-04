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
    strength: int

    def choose_meld_indexes(
        self,
        hand: list[Card],
        opening_required: bool,
        opening_minimum: int = OPENING_MELD_MINIMUM,
    ) -> list[int] | None: ...

    def choose_discard_index(self, hand: list[Card]) -> int: ...


@dataclass
class RandomBot:
    """Random bot: chooses Legal moves stochastically."""

    rng: random.Random
    name: str = "random"
    strength: int = 1

    def choose_meld_indexes(
        self,
        hand: list[Card],
        opening_required: bool,
        opening_minimum: int = OPENING_MELD_MINIMUM,
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(
            hand, opening_required, opening_minimum
        )
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
    strength: int = 1

    def choose_meld_indexes(
        self,
        hand: list[Card],
        opening_required: bool,
        opening_minimum: int = OPENING_MELD_MINIMUM,
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(
            hand, opening_required, opening_minimum
        )
        if not opening_required and self.strength >= 50:
            candidates = candidates + _wild_augmented_candidates(hand)
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

        rank_counts = _rank_counts(hand)
        if self.strength < 34:
            # Baseline: lowest immediate points, with weak wild-card protection.
            return min(
                safe,
                key=lambda idx: (hand_score([hand[idx]]), hand[idx].is_wild()),
            )

        if self.strength < 67:
            # Mid tier: avoid wilds first, then low points.
            return min(
                safe,
                key=lambda idx: (hand[idx].is_wild(), hand_score([hand[idx]])),
            )

        # High tier: avoid wilds, preserve grouped ranks, then prefer freeze pressure.
        def discard_key(idx: int) -> tuple[int, int, int, int]:
            card = hand[idx]
            wild_penalty = 1 if card.is_wild() else 0
            grouped_penalty = 1 if rank_counts[card.rank] > 1 else 0
            freeze_bonus = 0 if card.is_black_three() else 1
            points = hand_score([card])
            return (wild_penalty, grouped_penalty, freeze_bonus, points)

        return min(safe, key=discard_key)


@dataclass
class SafeBot:
    """Conservative bot: cautious melding and low-risk discard preferences."""

    name: str = "safe"
    strength: int = 1

    def choose_meld_indexes(
        self,
        hand: list[Card],
        opening_required: bool,
        opening_minimum: int = OPENING_MELD_MINIMUM,
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(
            hand, opening_required, opening_minimum
        )

        if not opening_required:
            # Tiered post-opening meld conservatism.
            if self.strength < 20:
                # Very safe: never meld after opening.
                return None
            if self.strength < 50:
                # Conservative: only meld large natural groups (4+ cards).
                big = [c for c in candidates if len(c) >= 4]
                if not big:
                    return None
                return max(
                    big,
                    key=lambda idxs: (hand_score([hand[i] for i in idxs]), len(idxs)),
                )
            # Standard strength: meld any natural candidates.
            if self.strength >= 70:
                candidates = candidates + _wild_augmented_candidates(hand)
            if not candidates:
                return None
            return max(
                candidates,
                key=lambda idxs: (hand_score([hand[i] for i in idxs]), len(idxs)),
            )

        # Opening required: natural candidates only.
        if not candidates:
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
    strength: int = 1

    def choose_meld_indexes(
        self,
        hand: list[Card],
        opening_required: bool,
        opening_minimum: int = OPENING_MELD_MINIMUM,
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(
            hand, opening_required, opening_minimum
        )
        if not opening_required and self.strength >= 50:
            candidates = candidates + _wild_augmented_candidates(hand)
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

        if self.strength < 40:
            # Baseline aggro: dump highest points first; treat wilds as valuable.
            return max(
                safe,
                key=lambda idx: (hand_score([hand[idx]]), hand[idx].is_wild()),
            )

        # Stronger aggro: shed highest-point naturals; keep wilds for meld extension.
        non_wild = [idx for idx in safe if not hand[idx].is_wild()]
        discard_pool = non_wild if non_wild else safe
        return max(discard_pool, key=lambda idx: hand_score([hand[idx]]))


@dataclass
class PlannerBot:
    """Balanced bot: meld strong candidates, keep synergy, discard with medium risk."""

    name: str = "planner"
    strength: int = 1

    def choose_meld_indexes(
        self,
        hand: list[Card],
        opening_required: bool,
        opening_minimum: int = OPENING_MELD_MINIMUM,
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(
            hand, opening_required, opening_minimum
        )
        if not opening_required and self.strength >= 50:
            candidates = candidates + _wild_augmented_candidates(hand)
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

        if self.strength < 34:

            def discard_key(idx: int) -> tuple[int, int, int, int]:
                card = hand[idx]
                wild_penalty = 1 if card.is_wild() else 0
                grouped_penalty = 1 if rank_counts[card.rank] > 1 else 0
                freeze_bonus = 0 if card.is_black_three() else 1
                points = hand_score([card])
                return (wild_penalty, grouped_penalty, freeze_bonus, points)

            return min(safe, key=discard_key)

        def discard_key(idx: int) -> tuple[int, int, int, int, int]:
            card = hand[idx]
            # Keep wilds and keep pairs/triples for future melds when possible.
            wild_penalty = 1 if card.is_wild() else 0
            grouped_penalty = 1 if rank_counts[card.rank] > 1 else 0
            singleton_bonus = 0 if rank_counts[card.rank] == 1 else 1
            freeze_bonus = 0 if card.is_black_three() else 1
            points = hand_score([card])
            return (
                wild_penalty,
                grouped_penalty,
                singleton_bonus,
                freeze_bonus,
                points,
            )

        return min(safe, key=discard_key)


@dataclass
class AdaptiveBot:
    """Adaptive bot: scales smoothly from random at low strength to aggressive at high.

    Strength bands:
      1-25  (random):   meld and discard choices are random among legal options.
      26-50 (safe):     conservative — large natural groups only, defensive discards.
      51-75 (planner):  balanced — wild-assisted melds, preserve synergy cards.
      76-100 (aggro):   aggressive — meld the most, shed high-point naturals first.
    """

    rng: random.Random
    name: str = "adaptive"
    strength: int = 50

    def choose_meld_indexes(
        self,
        hand: list[Card],
        opening_required: bool,
        opening_minimum: int = OPENING_MELD_MINIMUM,
    ) -> list[int] | None:
        candidates = _eligible_natural_meld_candidates(
            hand, opening_required, opening_minimum
        )

        if self.strength <= 25:
            # Random tier: pick any legal candidate at random.
            if not candidates:
                return None
            return self.rng.choice(candidates)

        if self.strength <= 50:
            # Safe tier: conservative post-opening melding.
            if not opening_required:
                big = [c for c in candidates if len(c) >= 4]
                if not big:
                    return None
                return max(big, key=lambda idxs: (hand_score([hand[i] for i in idxs]), len(idxs)))
            if not candidates:
                return None
            return min(candidates, key=lambda idxs: (hand_score([hand[i] for i in idxs]), len(idxs)))

        if self.strength <= 75:
            # Planner tier: balanced, includes wild-assisted candidates post-opening.
            if not opening_required:
                candidates = candidates + _wild_augmented_candidates(hand)
            if not candidates:
                return None

            def _planner_meld_key(idxs: list[int]) -> tuple[int, int, int]:
                cards = [hand[i] for i in idxs]
                return (hand_score(cards), len(idxs), _natural_density(cards))

            return max(candidates, key=_planner_meld_key)

        # Aggro tier (76-100): meld as much as possible.
        if not opening_required:
            candidates = candidates + _wild_augmented_candidates(hand)
        if not candidates:
            return None
        return max(candidates, key=lambda idxs: (len(idxs), hand_score([hand[i] for i in idxs])))

    def choose_discard_index(self, hand: list[Card]) -> int:
        safe = [idx for idx, card in enumerate(hand) if can_discard(card)[0]]
        if not safe:
            raise RuleError("bot could not find a legal discard")

        if self.strength <= 25:
            # Random tier: discard at random.
            return self.rng.choice(safe)

        rank_counts = _rank_counts(hand)

        if self.strength <= 50:
            # Safe tier: prefer black threes, avoid wilds, shed singletons.
            def _safe_discard_key(idx: int) -> tuple[int, int, int, int]:
                card = hand[idx]
                freeze_bonus = 0 if card.is_black_three() else 1
                singleton_bonus = 0 if rank_counts[card.rank] == 1 else 1
                wild_penalty = 1 if card.is_wild() else 0
                return (freeze_bonus, wild_penalty, singleton_bonus, hand_score([card]))

            return min(safe, key=_safe_discard_key)

        if self.strength <= 75:
            # Planner tier: keep wilds, preserve grouped ranks.
            def _planner_discard_key(idx: int) -> tuple[int, int, int, int, int]:
                card = hand[idx]
                wild_penalty = 1 if card.is_wild() else 0
                grouped_penalty = 1 if rank_counts[card.rank] > 1 else 0
                singleton_bonus = 0 if rank_counts[card.rank] == 1 else 1
                freeze_bonus = 0 if card.is_black_three() else 1
                return (wild_penalty, grouped_penalty, singleton_bonus, freeze_bonus, hand_score([card]))

            return min(safe, key=_planner_discard_key)

        # Aggro tier: shed highest-point naturals, keep wilds.
        non_wild = [idx for idx in safe if not hand[idx].is_wild()]
        discard_pool = non_wild if non_wild else safe
        return max(discard_pool, key=lambda idx: hand_score([hand[idx]]))


def _eligible_natural_meld_candidates(
    hand: list[Card],
    opening_required: bool,
    opening_minimum: int = OPENING_MELD_MINIMUM,
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
            if points >= opening_minimum:
                candidates.append(candidate)
            per_rank.append(candidate)

        if opening_required and per_rank:
            rank_candidates.append(per_rank)

    if opening_required:
        # Opening meld may be split across multiple natural ranks in one action.
        split_candidates = _opening_split_candidates(
            hand, rank_candidates, opening_minimum
        )
        candidates.extend(split_candidates)

    return candidates


def _opening_split_candidates(
    hand: list[Card], rank_candidates: list[list[list[int]]], opening_minimum: int
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
        if points < opening_minimum:
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


def _wild_augmented_candidates(hand: list[Card]) -> list[list[int]]:
    """Find meld candidates combining 2+ same-rank naturals with wild cards.

    Generates natural-pair-plus-wild melds (e.g. K K Joker) that the
    natural-only candidate finder misses.  Only called for post-opening turns.
    """
    wild_idxs = [i for i, card in enumerate(hand) if card.is_wild()]
    if not wild_idxs:
        return []
    by_rank: dict[str, list[int]] = {}
    for i, card in enumerate(hand):
        if not card.is_wild():
            by_rank.setdefault(card.rank, []).append(i)
    candidates: list[list[int]] = []
    for nat_idxs in by_rank.values():
        if len(nat_idxs) < 2:
            continue  # need at least 2 naturals to satisfy naturals >= wilds
        for num_nats in range(2, len(nat_idxs) + 1):
            max_wilds = min(len(wild_idxs), num_nats)  # wilds must not exceed naturals
            for num_wilds in range(1, max_wilds + 1):
                if num_nats + num_wilds < 3:
                    continue
                candidates.append(nat_idxs[:num_nats] + wild_idxs[:num_wilds])
    return candidates


def _natural_density(cards: list[Card]) -> int:
    """Count natural cards in a list."""
    return sum(1 for card in cards if not card.is_wild())


def _rank_counts(hand: list[Card]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in hand:
        counts[card.rank] = counts.get(card.rank, 0) + 1
    return counts
