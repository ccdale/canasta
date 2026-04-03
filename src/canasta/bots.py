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


def build_bot(kind: BotKind, seed: int | None = None) -> TurnBot:
    """Instantiate a bot of the given kind.

    Args:
        kind: The bot strategy type.
        seed: Random seed (only used by RandomBot).

    Returns:
        A TurnBot implementing the requested strategy.

    Raises:
        ValueError: If kind is not a valid BotKind.
    """
    if kind == "random":
        return RandomBot(rng=random.Random(seed))
    if kind == "greedy":
        return GreedyBot()
    if kind == "safe":
        return SafeBot()
    if kind == "aggro":
        return AggroBot()
    if kind == "planner":
        return PlannerBot()
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
