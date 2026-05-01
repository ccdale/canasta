"""Main GUI application for Canasta."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from canasta.bot_strategies import TurnBot
from canasta.bots import build_bot
from canasta.card_assets import asset_dir
from canasta.engine import CanastaEngine
from canasta.gui.bootstrap import parse_args, reexec_with_system_python
from canasta.gui.bot_runner import BotRunner, set_glib_import
from canasta.gui.layout import build_game_layout
from canasta.gui.lifecycle import (
    check_saved_game_on_startup,
    initial_status_message,
    load_saved_game,
    reset_game,
    run_action,
    show_new_game_dialog,
)
from canasta.gui.persistence import (
    get_version,
    load_game_stats,
)
from canasta.gui.renderer import GameRenderer
from canasta.gui.renderer import set_gtk_imports as set_renderer_gtk_imports
from canasta.gui.state import UIState
from canasta.gui.utilities import (
    new_cards_in_hand,
    resolve_target_meld_index,
)
from canasta.gui.widgets import set_gtk_imports
from canasta.model import PlayerId, RuleError

_BOT_CHOICES = ["human", "random", "greedy", "safe", "aggro", "planner"]

# Green-felt table CSS matching patience/ui/theme.py style.
_TABLE_CSS = """
@media (prefers-color-scheme: light) {
    .table-window {
        background-color: #dce6d7;
        background-image: linear-gradient(180deg, #edf3e9 0%, #dfe9d9 38%, #d3e0cd 100%);
    }
}
@media (prefers-color-scheme: dark) {
    .table-window {
        background-color: #132219;
        background-image: linear-gradient(180deg, #1b2d22 0%, #14251b 42%, #0e1b14 100%);
    }
}
.section-label { font-weight: bold; }
.hand-card {
    padding: 2px;
    min-width: 0;
    min-height: 0;
}
.draw-preview-new {
    border: 2px solid #f4b400;
    border-radius: 8px;
}
.canasta-card-shell {
    border: 2px solid #d4af37;
    border-radius: 8px;
    padding: 2px;
}
"""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        import gi

        gi.require_version("Gdk", "4.0")
        gi.require_version("Gtk", "4.0")
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk
    except ModuleNotFoundError:
        exit_code = reexec_with_system_python(argv or sys.argv[1:])
        if exit_code is not None:
            return exit_code
        print(
            "GTK4 GUI requires PyGObject (gi). Install python3-gi or pygobject, "
            "or launch with a system Python that provides GTK4 bindings.",
            file=sys.stderr,
        )
        return 1

    # Initialize widget module with GTK imports
    set_gtk_imports(Gtk, Gdk, GdkPixbuf)
    set_renderer_gtk_imports(Gtk)
    set_glib_import(GLib)

    def _install_css() -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        provider = Gtk.CssProvider()
        provider.load_from_string(_TABLE_CSS)
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_controllers(args: argparse.Namespace) -> dict[PlayerId, TurnBot | None]:
        controllers: dict[PlayerId, TurnBot | None] = {
            PlayerId.NORTH: None,
            PlayerId.SOUTH: None,
        }
        if args.north != "human":
            controllers[PlayerId.NORTH] = build_bot(args.north, seed=args.bot_seed + 1)
        if args.south != "human":
            controllers[PlayerId.SOUTH] = build_bot(args.south, seed=args.bot_seed + 2)
        return controllers

    class CanastaWindow(Gtk.ApplicationWindow):
        def __init__(self, app: Gtk.Application, args: argparse.Namespace) -> None:
            super().__init__(application=app)
            self.set_title(f"Canasta v{get_version()}")
            self.set_default_size(1280, 900)
            self.add_css_class("table-window")

            self.engine = CanastaEngine()
            self._north = args.north
            self._south = args.south
            self._bot_seed = args.bot_seed
            self.controllers = _build_controllers(args)
            # UI state management
            self.ui_state = UIState()
            self.bot_runner = BotRunner(self)
            self.renderer = GameRenderer(self)

            # Load game statistics
            stats = load_game_stats()
            self.north_wins = stats["north_wins"]
            self.south_wins = stats["south_wins"]
            self.assets_root = (
                Path(args.assets_dir).expanduser() if args.assets_dir else asset_dir()
            )

            build_game_layout(self, Gtk)

            self._set_status(self._initial_status_message())
            self._refresh()
            self._check_saved_game_on_startup()
            self._maybe_play_bot_turn()

        def _cancel_bot_timer(self) -> None:
            self.bot_runner.cancel_timer()

        def _cancel_draw_preview(self) -> None:
            if self.ui_state.draw_preview_timeout_id is not None:
                GLib.source_remove(self.ui_state.draw_preview_timeout_id)
            self.ui_state.reset_draw_preview()

        def _clear_draw_preview(self) -> bool:
            self.ui_state.draw_preview_timeout_id = None
            self.ui_state.draw_preview_base_hand = None
            self.ui_state.draw_preview_inserted_cards = None
            if self.ui_state.draw_preview_restore_scroll is not None:
                hadj = self.hand_scroll.get_hadjustment()
                hadj.set_value(self.ui_state.draw_preview_restore_scroll)
                self.ui_state.draw_preview_restore_scroll = None
            self._refresh()
            return False

        def _start_bot_indicator(self, actor: PlayerId, name: str) -> None:
            self.bot_runner.start_indicator(actor, name)

        def _stop_bot_indicator(self) -> None:
            self.bot_runner.stop_indicator()

        def _tick_bot_indicator(self) -> bool:
            return self.bot_runner.tick_indicator()

        def _maybe_play_bot_turn(self) -> None:
            self.bot_runner.maybe_play_turn()

        def _play_one_bot_turn(self) -> bool:
            return self.bot_runner.play_one_turn()

        def _reset_game(self, north: str, south: str, bot_seed: int) -> None:
            reset_game(self, north, south, bot_seed)

        def _load_saved_game(self) -> None:
            load_saved_game(self)

        def _check_saved_game_on_startup(self) -> None:
            check_saved_game_on_startup(self, self._show_new_game_dialog)

        def _show_new_game_dialog(self, _button: Gtk.Button) -> None:
            show_new_game_dialog(self, _BOT_CHOICES, self._reset_game)

        def _initial_status_message(self) -> str:
            return initial_status_message(self)

        def _clear_box(self, box: Gtk.Widget) -> None:
            child = box.get_first_child()
            while child is not None:
                next_child = child.get_next_sibling()
                box.remove(child)
                child = next_child

        def _set_status(self, message: str) -> None:
            self.status_label.set_text(message)

        def _update_stats_display(self) -> None:
            """Update the displayed game statistics."""
            self.stats_label.set_text(
                f"All-time record: North {self.north_wins} wins | South {self.south_wins} wins"
            )

        def _selected_indexes(self) -> list[int]:
            return sorted(self.ui_state.selected_hand_indexes)

        def _refresh_summary(self) -> None:
            self.renderer.refresh_summary()

        def _viewer_player_id(self) -> PlayerId:
            """Player whose hand is displayed: the human player, or SOUTH for bot-vs-bot."""
            for pid in (PlayerId.SOUTH, PlayerId.NORTH):
                if self.controllers.get(pid) is None:
                    return pid
            return PlayerId.SOUTH

        def _refresh_hand(self) -> None:
            self.renderer.refresh_hand()

        def _refresh_melds(self) -> None:
            self.renderer.refresh_melds()

        def _refresh_controls(self) -> None:
            self.renderer.refresh_controls()

        def _refresh(self) -> None:
            self.renderer.refresh()

        def _run_action(self, callback) -> None:
            run_action(self, callback)

        def _on_hand_toggled(self, button: Gtk.ToggleButton, index: int) -> None:
            if button.get_active():
                self.ui_state.selected_hand_indexes.add(index)
            else:
                self.ui_state.selected_hand_indexes.discard(index)
            self._refresh_summary()
            self._refresh_controls()

        def _on_deselect_all(self, _button: Gtk.Button) -> None:
            self.ui_state.selected_hand_indexes.clear()
            self._refresh_hand()
            self._refresh_summary()
            self._refresh_controls()

        def _on_draw(self, _button: Gtk.Button) -> None:
            self._cancel_draw_preview()
            before_hand = list(self.engine.current_hand())
            try:
                result = self.engine.draw_stock()
                self.ui_state.selected_hand_indexes.clear()
                self._set_status(result.message)
            except RuleError as exc:
                self._set_status(f"error: {exc}")
                self._refresh()
                self._maybe_play_bot_turn()
                return

            after_hand = list(self.engine.current_hand())
            inserted = new_cards_in_hand(before_hand, after_hand)
            if inserted:
                # Show newly inserted cards at draw/pickup position briefly.
                self.ui_state.draw_preview_base_hand = before_hand
                self.ui_state.draw_preview_inserted_cards = inserted
                hadj = self.hand_scroll.get_hadjustment()
                self.ui_state.draw_preview_restore_scroll = hadj.get_value()
                self.ui_state.draw_preview_timeout_id = GLib.timeout_add(
                    1000, self._clear_draw_preview
                )

            self._refresh()
            if inserted:
                hadj = self.hand_scroll.get_hadjustment()
                hadj.set_value(max(0.0, hadj.get_upper() - hadj.get_page_size()))
            self._maybe_play_bot_turn()

        def _on_pickup(self, _button: Gtk.Button) -> None:
            indexes = self._selected_indexes()
            self._run_action(lambda: self.engine.pickup_discard(indexes))

        def _on_meld(self, _button: Gtk.Button) -> None:
            indexes = self._selected_indexes()
            self._run_action(lambda: self.engine.create_meld(indexes))

        def _on_add_to_meld(self, _button: Gtk.Button) -> None:
            indexes = self._selected_indexes()
            current = self.engine.state.players[self.engine.state.current_player]
            cards = [current.hand[idx] for idx in indexes]
            try:
                meld_idx = resolve_target_meld_index(current.melds, cards)
            except RuleError as exc:
                self._set_status(f"error: {exc}")
                self._refresh_controls()
                return

            if meld_idx is None:
                dropdown_idx = self.meld_selector.get_selected()
                if dropdown_idx >= len(self.ui_state.meld_index_mapping):
                    self._set_status("error: select a meld first")
                    self._refresh_controls()
                    return
                # Map dropdown index to actual meld index
                meld_idx = self.ui_state.meld_index_mapping[dropdown_idx]

            self._run_action(lambda: self.engine.add_to_meld(meld_idx, indexes))

        def _on_discard(self, _button: Gtk.Button) -> None:
            indexes = self._selected_indexes()
            if len(indexes) != 1:
                self._set_status("error: select exactly one card to discard")
                self._refresh_controls()
                return
            self._run_action(lambda: self.engine.discard(indexes[0]))

        def _on_next_round(self, _button: Gtk.Button) -> None:
            self.ui_state.last_winner = (
                None  # Reset winner tracking when moving to next round
            )
            self._run_action(self.engine.next_round)

    class CanastaApplication(Gtk.Application):
        def __init__(self, args: argparse.Namespace) -> None:
            super().__init__(
                application_id="org.canasta.gtk", flags=Gio.ApplicationFlags.FLAGS_NONE
            )
            self.args = args

        def do_activate(self) -> None:
            active_window = self.get_active_window()
            if active_window is not None:
                active_window.present()
            else:
                _install_css()
                window = CanastaWindow(self, self.args)
                window.present()

    app = CanastaApplication(args)
    return app.run(None)


if __name__ == "__main__":
    sys.exit(main())
