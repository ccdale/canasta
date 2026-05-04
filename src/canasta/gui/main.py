"""Main GUI application for Canasta."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from canasta.card_assets import asset_dir
from canasta.engine import CanastaEngine
from canasta.gui.actions import (
    on_add_to_meld,
    on_deselect_all,
    on_discard,
    on_discard_pile_clicked,
    on_draw,
    on_hand_toggled,
    on_meld,
    on_next_round,
    on_pickup,
    on_reminder,
)
from canasta.gui.bootstrap import parse_args, reexec_with_system_python
from canasta.gui.bot_runner import BotRunner, set_glib_import
from canasta.gui.layout import build_game_layout
from canasta.gui.lifecycle import (
    build_controllers,
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
from canasta.gui.theme import install_css
from canasta.gui.theme import set_gtk_imports as set_theme_gtk_imports
from canasta.gui.widgets import set_gtk_imports
from canasta.model import PlayerId

_BOT_CHOICES = ["human", "random", "greedy", "safe", "aggro", "planner", "adaptive"]


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
    set_theme_gtk_imports(Gtk, Gdk)
    set_glib_import(GLib)

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
            self._bot_strength = args.bot_strength
            self.controllers = build_controllers(
                args.north,
                args.south,
                args.bot_seed,
                args.bot_strength,
            )
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
            self._set_bot_light(thinking=False)

            self._set_status(self._initial_status_message())
            self._refresh()
            self._check_saved_game_on_startup()
            self.bot_runner.maybe_play_turn()

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

        def _reset_game(
            self, north: str, south: str, bot_seed: int, bot_strength: int
        ) -> None:
            reset_game(self, north, south, bot_seed, bot_strength)

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

        def _set_bot_light(
            self,
            *,
            thinking: bool,
            actor: PlayerId | None = None,
            name: str = "",
        ) -> None:
            self.bot_light_label.remove_css_class("bot-light-thinking")
            self.bot_light_label.remove_css_class("bot-light-ready")
            if thinking:
                self.bot_light_label.add_css_class("bot-light-thinking")
                if actor is not None and name:
                    self.bot_light_label.set_text(
                        f"● Bot thinking: {actor.value}:{name}"
                    )
                else:
                    self.bot_light_label.set_text("● Bot thinking")
                return
            self.bot_light_label.add_css_class("bot-light-ready")
            self.bot_light_label.set_text("● Bot ready")

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
            on_hand_toggled(self, button, index)

        def _on_deselect_all(self, _button: Gtk.Button) -> None:
            on_deselect_all(self)

        def _on_draw(self, _button: Gtk.Button) -> None:
            on_draw(self, GLib)

        def _on_pickup(self, _button: Gtk.Button) -> None:
            on_pickup(self)

        def _on_meld(self, _button: Gtk.Button) -> None:
            on_meld(self)

        def _on_add_to_meld(self, _button: Gtk.Button) -> None:
            on_add_to_meld(self)

        def _on_discard(self, _button: Gtk.Button) -> None:
            on_discard(self)

        def _on_next_round(self, _button: Gtk.Button) -> None:
            on_next_round(self)

        def _on_discard_pile_clicked(self) -> None:
            on_discard_pile_clicked(self)

        def _on_reminder(self, _button: Gtk.Button) -> None:
            on_reminder(self)

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
                install_css()
                window = CanastaWindow(self, self.args)
                window.present()

    app = CanastaApplication(args)
    return app.run(None)


if __name__ == "__main__":
    sys.exit(main())
