from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, Protocol

from canasta.engine import CanastaEngine, RuleError
from canasta.model import Card
from canasta.rules import (
    OPENING_MELD_MINIMUM,
    can_discard,
    hand_score,
    opening_meld_value,
)

BotKind = Literal["random", "greedy", "safe"]


class TurnBot(Protocol):
    name: str

    def choose_meld_indexes(
        self, hand: list[Card], opening_required: bool
    ) -> list[int] | None: ...

    def choose_discard_index(self, hand: list[Card]) -> int: ...


@dataclass
class RandomBot:
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


def build_bot(kind: BotKind, seed: int | None = None) -> TurnBot:
    if kind == "random":
        return RandomBot(rng=random.Random(seed))
    if kind == "greedy":
        return GreedyBot()
    if kind == "safe":
        return SafeBot()
    raise ValueError(f"unknown bot kind: {kind}")


def play_bot_turn(engine: CanastaEngine, bot: TurnBot) -> list[str]:
    """Play a full bot turn and return readable action summaries."""
    actions: list[str] = []
    actions.append(engine.draw_stock().message)

    while True:
        player = engine.state.players[engine.state.current_player]
        opening_required = len(player.melds) == 0
        meld_indexes = bot.choose_meld_indexes(engine.current_hand(), opening_required)
        if meld_indexes is None:
            break
        try:
            actions.append(engine.create_meld(meld_indexes).message)
        except RuleError:
            break

    discard_idx = bot.choose_discard_index(engine.current_hand())
    actions.append(engine.discard(discard_idx).message)
    return actions


def _eligible_natural_meld_candidates(
    hand: list[Card], opening_required: bool
) -> list[list[int]]:
    by_rank: dict[str, list[int]] = {}
    for idx, card in enumerate(hand):
        if card.is_wild() or card.rank == "JOKER":
            continue
        by_rank.setdefault(card.rank, []).append(idx)

    candidates: list[list[int]] = []
    for indexes in by_rank.values():
        if len(indexes) < 3:
            continue
        for size in range(3, len(indexes) + 1):
            candidate = indexes[:size]
            if opening_required:
                points = opening_meld_value([hand[i] for i in candidate])
                if points < OPENING_MELD_MINIMUM:
                    continue
            candidates.append(candidate)
    return candidates
