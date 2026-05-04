"""Bot factory and turn orchestration for Canasta."""

import random
from typing import Literal

from canasta.bot_strategies import (
    AggroBot,
    GreedyBot,
    PlannerBot,
    RandomBot,
    SafeBot,
    TurnBot,
)
from canasta.engine import CanastaEngine
from canasta.model import RuleError
from canasta.rules import (
    discard_pile_is_frozen,
    opening_meld_value,
    validate_pickup_cards,
)

BotKind = Literal["random", "greedy", "safe", "aggro", "planner"]


def build_bot(kind: BotKind, seed: int | None = None, strength: int = 1) -> TurnBot:
    """Instantiate a bot of the given kind.

    Args:
        kind: The bot strategy type.
        seed: Random seed (only used by RandomBot).
        strength: Bot strength from 1-100.

    Returns:
        A TurnBot implementing the requested strategy.

    Raises:
        ValueError: If kind is not a valid BotKind.
    """
    if strength < 1 or strength > 100:
        raise ValueError("bot strength must be between 1 and 100")

    if kind == "random":
        return RandomBot(rng=random.Random(seed), strength=strength)
    if kind == "greedy":
        return GreedyBot(strength=strength)
    if kind == "safe":
        return SafeBot(strength=strength)
    if kind == "aggro":
        return AggroBot(strength=strength)
    if kind == "planner":
        return PlannerBot(strength=strength)
    raise ValueError(f"unknown bot kind: {kind}")


def play_bot_turn(engine: CanastaEngine, bot: TurnBot) -> list[str]:
    """Play a full bot turn and return readable action summaries.

    Args:
        engine: The game engine.
        bot: The bot taking the turn.

    Returns:
        List of action message strings describing what the bot did.
    """
    actions: list[str] = []
    pickup_indexes = _choose_pickup_indexes(engine, bot)
    if pickup_indexes is not None:
        try:
            actions.append(engine.pickup_discard(pickup_indexes).message)
        except RuleError:
            actions.append(engine.draw_stock().message)
    else:
        actions.append(engine.draw_stock().message)

    while True:
        player = engine.state.players[engine.state.current_player]
        opening_required = len(player.melds) == 0
        opening_minimum = engine.opening_meld_minimum(engine.state.current_player)
        hand = engine.current_hand()
        meld_indexes = bot.choose_meld_indexes(hand, opening_required, opening_minimum)
        if meld_indexes is None:
            break
        try:
            # If cards match an existing meld's rank, extend it rather than
            # creating a duplicate meld of the same rank.
            chosen_cards = [hand[i] for i in meld_indexes]
            natural_rank = next((c.rank for c in chosen_cards if not c.is_wild()), None)
            existing_idx = next(
                (
                    idx
                    for idx, m in enumerate(player.melds)
                    if m.natural_rank == natural_rank
                ),
                None,
            )
            if existing_idx is not None:
                actions.append(engine.add_to_meld(existing_idx, meld_indexes).message)
            else:
                actions.append(engine.create_meld(meld_indexes).message)
        except RuleError:
            break

    discard_idx = bot.choose_discard_index(engine.current_hand())
    actions.append(engine.discard(discard_idx).message)
    return actions


def _choose_pickup_indexes(engine: CanastaEngine, bot: TurnBot) -> list[int] | None:
    """Return hand indexes for a legal pickup candidate, if one exists."""
    if bot.strength < 50:
        return None
    if engine.state.turn_drawn or not engine.state.discard:
        return None

    top_discard = engine.state.discard[-1]
    hand = engine.current_hand()
    naturals_same_rank = [
        idx
        for idx, card in enumerate(hand)
        if not card.is_wild() and card.rank == top_discard.rank
    ]
    wilds = [idx for idx, card in enumerate(hand) if card.is_wild()]

    candidates: list[list[int]] = []
    frozen = discard_pile_is_frozen(engine.state.discard)
    if frozen:
        if len(naturals_same_rank) >= 2:
            candidates.append([naturals_same_rank[0], naturals_same_rank[1]])
    else:
        if len(naturals_same_rank) >= 2:
            candidates.append([naturals_same_rank[0], naturals_same_rank[1]])
        if naturals_same_rank and wilds:
            candidates.append([naturals_same_rank[0], wilds[0]])

    if not candidates:
        return None

    player = engine.state.players[engine.state.current_player]
    opening_required = len(player.melds) == 0
    opening_minimum = engine.opening_meld_minimum(engine.state.current_player)

    legal: list[tuple[list[int], int, int]] = []
    for candidate in candidates:
        hand_cards = [hand[i] for i in candidate]
        groups, _ = validate_pickup_cards(
            top_discard, hand_cards, allow_multi_rank=opening_required
        )
        if groups is None:
            continue
        opening_value = sum(opening_meld_value(group) for group in groups)
        if opening_required and opening_value < opening_minimum:
            continue
        natural_count = sum(1 for card in hand_cards if not card.is_wild())
        legal.append((candidate, opening_value, natural_count))

    if not legal:
        return None

    # Prefer higher opening value and natural density for stable, safer pickup.
    best, _, _ = max(legal, key=lambda row: (row[1], row[2]))
    return best
