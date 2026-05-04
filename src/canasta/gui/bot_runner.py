"""Bot turn scheduling helpers for the Canasta GTK UI."""

from __future__ import annotations

from canasta.bots import play_bot_turn
from canasta.model import PlayerId, RuleError

GLib = None


def set_glib_import(glib) -> None:
    """Set the deferred GLib import used for bot timers."""
    global GLib
    GLib = glib


class BotRunner:
    """Encapsulate bot turn scheduling and thinking indicator updates."""

    def __init__(self, window) -> None:
        self.window = window

    def cancel_timer(self) -> None:
        if self.window.ui_state.bot_timeout_id is not None:
            GLib.source_remove(self.window.ui_state.bot_timeout_id)
            self.window.ui_state.bot_timeout_id = None
        self.stop_indicator()

    def start_indicator(self, actor: PlayerId, name: str) -> None:
        self.stop_indicator()
        self.window.ui_state.bot_indicator_actor = actor
        self.window.ui_state.bot_indicator_name = name
        self.window.ui_state.bot_indicator_step = 0
        self.window._set_bot_light(thinking=True, actor=actor, name=name)
        self.window._set_status(f"[{actor.value}:{name}] thinking")
        self.window.ui_state.bot_indicator_timeout_id = GLib.timeout_add(
            250, self.tick_indicator
        )

    def stop_indicator(self) -> None:
        if self.window.ui_state.bot_indicator_timeout_id is not None:
            GLib.source_remove(self.window.ui_state.bot_indicator_timeout_id)
        self.window.ui_state.bot_indicator_timeout_id = None
        self.window.ui_state.bot_indicator_actor = None
        self.window.ui_state.bot_indicator_name = ""
        self.window.ui_state.bot_indicator_step = 0
        self.window._set_bot_light(thinking=False)

    def tick_indicator(self) -> bool:
        if self.window.ui_state.bot_indicator_actor is None:
            return False
        suffix = "." * ((self.window.ui_state.bot_indicator_step % 3) + 1)
        self.window._set_status(
            f"[{self.window.ui_state.bot_indicator_actor.value}:{self.window.ui_state.bot_indicator_name}] thinking{suffix}"
        )
        self.window.ui_state.bot_indicator_step += 1
        return True

    def maybe_play_turn(self) -> None:
        """If the current player is bot-controlled, auto-play their full turn."""
        if self.window.ui_state.bot_timeout_id is not None:
            return
        state = self.window.engine.state
        if state.winner is not None:
            return
        controller = self.window.controllers.get(state.current_player)
        if controller is None:
            return
        self.start_indicator(state.current_player, controller.name)
        self.window._refresh_controls()
        self.window.ui_state.bot_timeout_id = GLib.timeout_add(1000, self.play_one_turn)

    def play_one_turn(self) -> bool:
        """Play one bot turn, then optionally schedule the next bot seat."""
        self.window.ui_state.bot_timeout_id = None
        state = self.window.engine.state
        if state.winner is not None:
            self.stop_indicator()
            return False
        controller = self.window.controllers.get(state.current_player)
        if controller is None:
            self.stop_indicator()
            return False
        try:
            actor = state.current_player
            actions = play_bot_turn(self.window.engine, controller)
            bot_message = f"[{actor.value}:{controller.name}] " + " | ".join(actions)
            self.window.ui_state.last_bot_move_message = bot_message
            self.window._set_status(bot_message)
        except RuleError as exc:
            bot_message = (
                f"[{state.current_player.value}:{controller.name}] error: {exc}"
            )
            self.window.ui_state.last_bot_move_message = bot_message
            self.window._set_status(bot_message)
            self.window._refresh()
            self.stop_indicator()
            return False

        self.window._refresh()
        self.stop_indicator()
        self.maybe_play_turn()
        return False
