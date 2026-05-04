"""Game lifecycle helpers for the Canasta GTK window."""

from __future__ import annotations

from collections.abc import Callable

from canasta.bot_strategies import TurnBot
from canasta.bots import build_bot
from canasta.engine import CanastaEngine
from canasta.gui.dialogs import create_new_game_dialog, create_resume_game_dialog
from canasta.gui.persistence import load_game, save_game
from canasta.model import PlayerId, RuleError


def build_controllers(
    north: str, south: str, bot_seed: int, bot_strength: int
) -> dict[PlayerId, TurnBot | None]:
    """Create seat controller mapping from requested bot/human variants."""
    return {
        PlayerId.NORTH: build_bot(north, seed=bot_seed + 1, strength=bot_strength)
        if north != "human"
        else None,
        PlayerId.SOUTH: build_bot(south, seed=bot_seed + 2, strength=bot_strength)
        if south != "human"
        else None,
    }


def reset_game(
    window, north: str, south: str, bot_seed: int, bot_strength: int
) -> None:
    """Start a fresh game with the provided seat controllers."""
    window.bot_runner.cancel_timer()
    window._cancel_draw_preview()
    window._north = north
    window._south = south
    window._bot_seed = bot_seed
    window._bot_strength = bot_strength
    window.controllers = build_controllers(north, south, bot_seed, bot_strength)
    window.engine = CanastaEngine()
    window.ui_state.reset_selection()
    window.ui_state.last_bot_move_message = ""
    window.ui_state.last_winner = None
    window._set_status(initial_status_message(window))
    window._refresh()
    save_game(window.engine.state)
    window.bot_runner.maybe_play_turn()


def load_saved_game(window) -> None:
    """Load and restore a previously saved game."""
    saved_state = load_game()
    if saved_state is None:
        window._set_status("error: could not load saved game")
        return

    window.bot_runner.cancel_timer()
    window._cancel_draw_preview()
    # Preserve current controller setup since we don't store it.
    window.engine.state = saved_state
    window.ui_state.reset_selection()
    window.ui_state.last_bot_move_message = ""
    window.ui_state.last_winner = None
    window._set_status("Game restored from save")
    window._refresh()
    window.bot_runner.maybe_play_turn()


def check_saved_game_on_startup(window, on_new_game: Callable) -> None:
    """Offer the user a chance to resume when a save exists."""
    create_resume_game_dialog(
        window,
        on_resume=window._load_saved_game,
        on_new_game=on_new_game,
    )


def show_new_game_dialog(window, bot_choices: list[str], on_reset: Callable) -> None:
    """Open the new game configuration dialog."""
    create_new_game_dialog(
        window,
        window._north,
        window._south,
        window._bot_seed,
        window._bot_strength,
        bot_choices,
        on_reset,
    )


def initial_status_message(window) -> str:
    """Compose status text shown at startup/new-game transitions."""
    if not window.assets_root.exists():
        return (
            f"Card images not found at {window.assets_root}. "
            "Using text fallback. Symlink ~/.local/share/canasta to your card images."
        )
    controllers_desc = f"north={window._north}  south={window._south}"
    return (
        f"Assets: {window.assets_root}  |  {controllers_desc}  |  "
        f"bot_strength={window._bot_strength}"
    )


def run_action(window, callback: Callable) -> None:
    """Run a game action, refresh the UI, and trigger autosave/bot response."""
    window._cancel_draw_preview()
    try:
        result = callback()
        window.ui_state.selected_hand_indexes.clear()
        window._set_status(result.message)
    except RuleError as exc:
        window._set_status(f"error: {exc}")
    window._refresh()
    save_game(window.engine.state)
    window.bot_runner.maybe_play_turn()
