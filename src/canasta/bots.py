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
