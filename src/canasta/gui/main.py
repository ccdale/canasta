"""Main GUI application for Canasta."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from canasta.bot_strategies import TurnBot
from canasta.bots import build_bot, play_bot_turn
from canasta.card_assets import asset_dir, back_image_path, card_image_path
from canasta.engine import CanastaEngine
from canasta.gui.bootstrap import parse_args, reexec_with_system_python
from canasta.gui.persistence import (
    get_version,
    has_saved_game,
    load_game,
    load_game_stats,
    save_game,
    save_game_stats,
)
from canasta.gui.utilities import (
    format_card,
    new_cards_in_hand,
    rank_sort_key,
    reorganize_meld_cards,
    resolve_target_meld_index,
)
from canasta.gui.widgets import (
    CARD_H,
    CARD_LIFT,
    CARD_PEEK,
    CARD_W,
    MELD_PEEK,
    build_card_widget,
    build_fanned_cards,
    build_pile_picture,
    set_gtk_imports,
)
from canasta.model import Card, PlayerId, RuleError
from canasta.rules import discard_pile_is_frozen

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
            self.selected_hand_indexes: set[int] = set()
            self._meld_index_mapping: list[
                int
            ] = []  # Maps dropdown index to actual meld index

            # Load game statistics
            stats = load_game_stats()
            self.north_wins = stats["north_wins"]
            self.south_wins = stats["south_wins"]
            self._last_winner: PlayerId | None = (
                None  # Track winner to detect new games
            )
            self._bot_timeout_id: int | None = None
            self._bot_indicator_timeout_id: int | None = None
            self._bot_indicator_actor: PlayerId | None = None
            self._bot_indicator_name: str = ""
            self._bot_indicator_step = 0
            self._draw_preview_timeout_id: int | None = None
            self._draw_preview_base_hand: list[Card] | None = None
            self._draw_preview_inserted_cards: list[Card] | None = None
            self._draw_preview_restore_scroll: float | None = None
            self.assets_root = (
                Path(args.assets_dir).expanduser() if args.assets_dir else asset_dir()
            )

            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            root.set_margin_top(8)
            root.set_margin_bottom(8)
            root.set_margin_start(8)
            root.set_margin_end(8)
            self.set_child(root)

            # ── Row 1: North melds ────────────────────────────────────────
            self.north_melds_hdr = Gtk.Label(label="North melds", xalign=0)
            self.north_melds_hdr.add_css_class("section-label")
            root.append(self.north_melds_hdr)
            north_melds_scroll = Gtk.ScrolledWindow()
            north_melds_scroll.set_policy(
                Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER
            )
            north_melds_scroll.set_min_content_height(CARD_H + 24)
            root.append(north_melds_scroll)
            self.north_melds_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=10
            )
            self.north_melds_box.set_margin_top(4)
            self.north_melds_box.set_margin_bottom(4)
            self.north_melds_box.set_margin_start(6)
            north_melds_scroll.set_child(self.north_melds_box)

            root.append(Gtk.Separator())

            # ── Row 2: Stock and discard (own row — nothing tall beside them) ──
            pile_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            pile_row.set_margin_start(6)
            pile_row.set_size_request(-1, CARD_H + 34)
            pile_row.set_valign(Gtk.Align.START)
            pile_row.set_vexpand(False)
            root.append(pile_row)

            self.stock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self.stock_box.set_size_request(CARD_W + 4, CARD_H + 28)
            self.stock_box.set_valign(Gtk.Align.START)
            self.stock_box.set_vexpand(False)
            pile_row.append(self.stock_box)

            self.discard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self.discard_box.set_size_request(CARD_W + 4, CARD_H + 28)
            self.discard_box.set_valign(Gtk.Align.START)
            self.discard_box.set_vexpand(False)
            pile_row.append(self.discard_box)

            # ── Row 3: Controls ───────────────────────────────────────────
            controls_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            controls_row.set_margin_start(6)
            root.append(controls_row)

            self.draw_button = Gtk.Button(label="Draw")
            self.draw_button.connect("clicked", self._on_draw)
            controls_row.append(self.draw_button)

            self.pickup_button = Gtk.Button(label="Pickup")
            self.pickup_button.connect("clicked", self._on_pickup)
            controls_row.append(self.pickup_button)

            self.meld_button = Gtk.Button(label="Meld")
            self.meld_button.connect("clicked", self._on_meld)
            controls_row.append(self.meld_button)

            self.add_button = Gtk.Button(label="Add to Meld")
            self.add_button.connect("clicked", self._on_add_to_meld)
            controls_row.append(self.add_button)

            self.discard_button = Gtk.Button(label="Discard")
            self.discard_button.connect("clicked", self._on_discard)
            controls_row.append(self.discard_button)

            self.deselect_all_button = Gtk.Button(label="Deselect All")
            self.deselect_all_button.connect("clicked", self._on_deselect_all)
            controls_row.append(self.deselect_all_button)

            self.next_round_button = Gtk.Button(label="Next Round")
            self.next_round_button.connect("clicked", self._on_next_round)
            controls_row.append(self.next_round_button)

            self.meld_model = Gtk.StringList.new([])
            self.meld_selector = Gtk.DropDown.new(self.meld_model, None)
            controls_row.append(self.meld_selector)

            new_game_button = Gtk.Button(label="New Game\u2026")
            new_game_button.connect("clicked", self._show_new_game_dialog)
            controls_row.append(new_game_button)

            # ── Row 4: Status ─────────────────────────────────────────────
            self.info_label = Gtk.Label(xalign=0)
            self.info_label.set_wrap(True)
            self.info_label.set_margin_start(6)
            root.append(self.info_label)

            self.score_label = Gtk.Label(xalign=0)
            self.score_label.set_wrap(True)
            self.score_label.set_margin_start(6)
            root.append(self.score_label)

            self.status_label = Gtk.Label(xalign=0)
            self.status_label.set_wrap(True)
            self.status_label.set_margin_start(6)
            root.append(self.status_label)

            self.stats_label = Gtk.Label(xalign=0)
            self.stats_label.set_wrap(True)
            self.stats_label.set_margin_start(6)
            root.append(self.stats_label)

            root.append(Gtk.Separator())

            # ── Row 5: South hand ─────────────────────────────────────────
            hand_hdr = Gtk.Label(label="Your hand", xalign=0)
            hand_hdr.add_css_class("section-label")
            hand_hdr.set_margin_start(6)
            root.append(hand_hdr)
            hand_scroll = Gtk.ScrolledWindow()
            hand_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
            hand_scroll.set_min_content_height(CARD_H + CARD_LIFT + 8)
            root.append(hand_scroll)
            self.hand_scroll = hand_scroll
            self.hand_fixed = Gtk.Fixed()
            hand_scroll.set_child(self.hand_fixed)

            root.append(Gtk.Separator())

            # ── Row 6: South melds ────────────────────────────────────────
            south_melds_hdr = Gtk.Label(label="South melds", xalign=0)
            south_melds_hdr.add_css_class("section-label")
            south_melds_hdr.set_margin_start(6)
            root.append(south_melds_hdr)
            south_melds_scroll = Gtk.ScrolledWindow()
            south_melds_scroll.set_policy(
                Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER
            )
            south_melds_scroll.set_min_content_height(CARD_H + 24)
            root.append(south_melds_scroll)
            self.south_melds_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=10
            )
            self.south_melds_box.set_margin_top(4)
            self.south_melds_box.set_margin_bottom(4)
            self.south_melds_box.set_margin_start(6)
            south_melds_scroll.set_child(self.south_melds_box)

            self._set_status(self._initial_status_message())
            self._refresh()
            self._check_saved_game_on_startup()
            self._maybe_play_bot_turn()

        def _cancel_bot_timer(self) -> None:
            if self._bot_timeout_id is not None:
                GLib.source_remove(self._bot_timeout_id)
                self._bot_timeout_id = None
            self._stop_bot_indicator()

        def _cancel_draw_preview(self) -> None:
            if self._draw_preview_timeout_id is not None:
                GLib.source_remove(self._draw_preview_timeout_id)
                self._draw_preview_timeout_id = None
            self._draw_preview_base_hand = None
            self._draw_preview_inserted_cards = None
            self._draw_preview_restore_scroll = None

        def _clear_draw_preview(self) -> bool:
            self._draw_preview_timeout_id = None
            self._draw_preview_base_hand = None
            self._draw_preview_inserted_cards = None
            if self._draw_preview_restore_scroll is not None:
                hadj = self.hand_scroll.get_hadjustment()
                hadj.set_value(self._draw_preview_restore_scroll)
                self._draw_preview_restore_scroll = None
            self._refresh()
            return False

        def _start_bot_indicator(self, actor: PlayerId, name: str) -> None:
            self._stop_bot_indicator()
            self._bot_indicator_actor = actor
            self._bot_indicator_name = name
            self._bot_indicator_step = 0
            self._set_status(f"[{actor.value}:{name}] thinking")
            self._bot_indicator_timeout_id = GLib.timeout_add(
                250, self._tick_bot_indicator
            )

        def _stop_bot_indicator(self) -> None:
            if self._bot_indicator_timeout_id is not None:
                GLib.source_remove(self._bot_indicator_timeout_id)
                self._bot_indicator_timeout_id = None
            self._bot_indicator_actor = None
            self._bot_indicator_name = ""
            self._bot_indicator_step = 0

        def _tick_bot_indicator(self) -> bool:
            if self._bot_indicator_actor is None:
                return False
            suffix = "." * ((self._bot_indicator_step % 3) + 1)
            self._set_status(
                f"[{self._bot_indicator_actor.value}:{self._bot_indicator_name}] thinking{suffix}"
            )
            self._bot_indicator_step += 1
            return True

        def _maybe_play_bot_turn(self) -> None:
            """If the current player is bot-controlled, auto-play their full turn."""
            if self._bot_timeout_id is not None:
                return
            state = self.engine.state
            if state.winner is not None:
                return
            controller = self.controllers.get(state.current_player)
            if controller is None:
                return
            self._start_bot_indicator(state.current_player, controller.name)
            self._refresh_controls()
            self._bot_timeout_id = GLib.timeout_add(1000, self._play_one_bot_turn)

        def _play_one_bot_turn(self) -> bool:
            """Play one bot turn, then optionally schedule the next bot seat."""
            self._bot_timeout_id = None
            self._stop_bot_indicator()
            state = self.engine.state
            if state.winner is not None:
                return False
            controller = self.controllers.get(state.current_player)
            if controller is None:
                return False
            try:
                actor = state.current_player
                actions = play_bot_turn(self.engine, controller)
                self._set_status(
                    f"[{actor.value}:{controller.name}] " + " | ".join(actions)
                )
            except RuleError as exc:
                self._set_status(
                    f"[{state.current_player.value}:{controller.name}] error: {exc}"
                )
                self._refresh()
                return False

            self._refresh()
            self._maybe_play_bot_turn()
            return False

        def _reset_game(self, north: str, south: str, bot_seed: int) -> None:
            self._cancel_bot_timer()
            self._cancel_draw_preview()
            self._north = north
            self._south = south
            self._bot_seed = bot_seed
            self.controllers = {
                PlayerId.NORTH: (
                    build_bot(north, seed=bot_seed + 1) if north != "human" else None
                ),
                PlayerId.SOUTH: (
                    build_bot(south, seed=bot_seed + 2) if south != "human" else None
                ),
            }
            self.engine = CanastaEngine()
            self.selected_hand_indexes.clear()
            self._meld_index_mapping = []
            self._last_winner = None  # Reset winner tracking for new game
            self._set_status(self._initial_status_message())
            self._refresh()
            # Auto-save newly started game
            save_game(self.engine.state)
            self._maybe_play_bot_turn()

        def _load_saved_game(self) -> None:
            """Load and restore a previously saved game."""
            saved_state = load_game()
            if saved_state is None:
                self._set_status("error: could not load saved game")
                return

            self._cancel_bot_timer()
            self._cancel_draw_preview()
            # Preserve current controller setup since we don't store it
            self.engine.state = saved_state
            self.selected_hand_indexes.clear()
            self._meld_index_mapping = []
            self._last_winner = None
            self._set_status("Game restored from save")
            self._refresh()
            self._maybe_play_bot_turn()

        def _check_saved_game_on_startup(self) -> None:
            """Check for saved game on startup and offer to resume if one exists."""
            if not has_saved_game():
                return

            dialog = Gtk.Window()
            dialog.set_title("Resume Game?")
            dialog.set_transient_for(self)
            dialog.set_modal(True)
            dialog.set_resizable(False)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.set_margin_top(16)
            box.set_margin_bottom(16)
            box.set_margin_start(16)
            box.set_margin_end(16)
            dialog.set_child(box)

            label = Gtk.Label(label="A saved game was found. Resume?")
            label.set_wrap(True)
            box.append(label)

            btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            btn_row.set_halign(Gtk.Align.END)

            new_btn = Gtk.Button(label="New Game")
            new_btn.connect(
                "clicked", lambda _: (dialog.close(), self._show_new_game_dialog(None))
            )
            btn_row.append(new_btn)

            resume_btn = Gtk.Button(label="Resume")
            resume_btn.add_css_class("suggested-action")
            resume_btn.connect(
                "clicked", lambda _: (dialog.close(), self._load_saved_game())
            )
            btn_row.append(resume_btn)

            box.append(btn_row)
            # Defer dialog presentation until after main window is realized
            GLib.idle_add(lambda: dialog.present() or False)

        def _show_new_game_dialog(self, _button: Gtk.Button) -> None:
            dialog = Gtk.Window()
            dialog.set_title("New Game")
            dialog.set_transient_for(self)
            dialog.set_modal(True)
            dialog.set_resizable(False)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.set_margin_top(16)
            box.set_margin_bottom(16)
            box.set_margin_start(16)
            box.set_margin_end(16)
            dialog.set_child(box)

            north_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            north_lbl = Gtk.Label(label="North seat:", xalign=0)
            north_lbl.set_hexpand(True)
            north_row.append(north_lbl)
            north_model = Gtk.StringList.new(_BOT_CHOICES)
            north_dd = Gtk.DropDown.new(north_model, None)
            north_dd.set_selected(_BOT_CHOICES.index(self._north))
            north_row.append(north_dd)
            box.append(north_row)

            south_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            south_lbl = Gtk.Label(label="South seat:", xalign=0)
            south_lbl.set_hexpand(True)
            south_row.append(south_lbl)
            south_model = Gtk.StringList.new(_BOT_CHOICES)
            south_dd = Gtk.DropDown.new(south_model, None)
            south_dd.set_selected(_BOT_CHOICES.index(self._south))
            south_row.append(south_dd)
            box.append(south_row)

            seed_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            seed_lbl = Gtk.Label(label="Bot seed:", xalign=0)
            seed_lbl.set_hexpand(True)
            seed_row.append(seed_lbl)
            adj = Gtk.Adjustment.new(self._bot_seed, 0, 9999, 1, 10, 0)
            seed_spin = Gtk.SpinButton.new(adj, 1, 0)
            seed_row.append(seed_spin)
            box.append(seed_row)

            btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            btn_row.set_halign(Gtk.Align.END)
            cancel_btn = Gtk.Button(label="Cancel")
            cancel_btn.connect("clicked", lambda _: dialog.close())
            btn_row.append(cancel_btn)
            start_btn = Gtk.Button(label="Start")
            start_btn.add_css_class("suggested-action")

            def _on_start(_btn: Gtk.Button) -> None:
                north = _BOT_CHOICES[north_dd.get_selected()]
                south = _BOT_CHOICES[south_dd.get_selected()]
                seed = int(seed_spin.get_value())
                dialog.close()
                self._reset_game(north, south, seed)

            start_btn.connect("clicked", _on_start)
            btn_row.append(start_btn)
            box.append(btn_row)

            dialog.present()

        def _initial_status_message(self) -> str:
            if not self.assets_root.exists():
                return (
                    f"Card images not found at {self.assets_root}. "
                    "Using text fallback. Symlink ~/.local/share/canasta to your card images."
                )
            controllers_desc = f"north={self._north}  south={self._south}"
            return f"Assets: {self.assets_root}  |  {controllers_desc}"

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
            return sorted(self.selected_hand_indexes)

        def _render_card_widget(self, card: Card, caption: str) -> Gtk.Widget:
            wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            wrapper.append(build_card_widget(card, self.assets_root, format_card))
            label = Gtk.Label(label=caption)
            wrapper.append(label)
            return wrapper

        def _refresh_summary(self) -> None:
            state = self.engine.state

            # Check if a new winner has been determined
            if state.winner is not None and state.winner != self._last_winner:
                self._last_winner = state.winner
                if state.winner == PlayerId.NORTH:
                    self.north_wins += 1
                else:
                    self.south_wins += 1
                save_game_stats(self.north_wins, self.south_wins)

            north = state.players[PlayerId.NORTH]
            self.north_melds_hdr.set_text(f"North  ({len(north.hand)} cards in hand)")

            self.info_label.set_text(
                "\n".join(
                    [
                        f"Round {state.round_number}  |  "
                        f"Current: {state.current_player.value}  |  "
                        + (
                            f"Winner: {state.winner.value}"
                            if state.winner is not None
                            else "No winner yet"
                        ),
                        f"Selected: {self._selected_indexes() or '(none)'}  |  "
                        f"Frozen: {discard_pile_is_frozen(state.discard)}  |  "
                        f"Turn drawn: {state.turn_drawn}  |  "
                        f"Hand: {len(state.players[self._viewer_player_id()].hand)} cards",
                    ]
                )
            )

            north_round = self.engine.score(PlayerId.NORTH)
            south_round = self.engine.score(PlayerId.SOUTH)
            north_total = self.engine.total_score(PlayerId.NORTH)
            south_total = self.engine.total_score(PlayerId.SOUTH)
            self.score_label.set_text(
                f"North: {north_round} pts (total {north_total})  |  "
                f"South: {south_round} pts (total {south_total})"
            )

            self._clear_box(self.stock_box)
            stock_title = Gtk.Label(label=f"Stock ({len(state.stock)})")
            stock_title.add_css_class("section-label")
            self.stock_box.append(stock_title)
            back_path = back_image_path(self.assets_root)
            if back_path is not None:
                self.stock_box.append(build_pile_picture(back_path))
            else:
                self.stock_box.append(Gtk.Label(label="[stock]"))

            self._clear_box(self.discard_box)
            discard_title = Gtk.Label(
                label=f"Discard ({len(state.discard)})"
                + (" \u2744" if discard_pile_is_frozen(state.discard) else "")
            )
            discard_title.add_css_class("section-label")
            self.discard_box.append(discard_title)
            if state.discard:
                top_discard = state.discard[-1]
                top_discard_path = card_image_path(top_discard, self.assets_root)
                if top_discard_path is not None:
                    self.discard_box.append(build_pile_picture(top_discard_path))
                else:
                    self.discard_box.append(
                        build_card_widget(top_discard, self.assets_root, format_card)
                    )
            else:
                self.discard_box.append(Gtk.Label(label="(empty)"))

        def _viewer_player_id(self) -> PlayerId:
            """Player whose hand is displayed: the human player, or SOUTH for bot-vs-bot."""
            for pid in (PlayerId.SOUTH, PlayerId.NORTH):
                if self.controllers.get(pid) is None:
                    return pid
            return PlayerId.SOUTH

        def _refresh_hand(self) -> None:
            self._clear_box(self.hand_fixed)
            current = self.engine.state.players[self._viewer_player_id()]
            preview_active = (
                self._draw_preview_base_hand is not None
                and self._draw_preview_inserted_cards is not None
            )

            if preview_active:
                base_hand = self._draw_preview_base_hand or []
                inserted_cards = self._draw_preview_inserted_cards or []
                base_w = (
                    max(CARD_W, (len(base_hand) - 1) * CARD_PEEK + CARD_W)
                    if base_hand
                    else 0
                )
                inserted_gap = 12 if base_hand and inserted_cards else 0
                inserted_stride = CARD_W + 8
                inserted_w = (
                    (len(inserted_cards) - 1) * inserted_stride + CARD_W
                    if inserted_cards
                    else 0
                )
                total_w = max(CARD_W, base_w + inserted_gap + inserted_w)
                self.hand_fixed.set_size_request(total_w, CARD_H + CARD_LIFT + 8)

                for idx, card in enumerate(base_hand):
                    shell = Gtk.Box()
                    shell.add_css_class("hand-card")
                    shell.append(build_card_widget(card, self.assets_root, format_card))
                    x = idx * CARD_PEEK
                    y = CARD_LIFT
                    self.hand_fixed.put(shell, x, y)

                start_x = base_w + inserted_gap
                for idx, card in enumerate(inserted_cards):
                    shell = Gtk.Box()
                    shell.add_css_class("hand-card")
                    shell.add_css_class("draw-preview-new")
                    shell.append(build_card_widget(card, self.assets_root, format_card))
                    x = start_x + idx * inserted_stride
                    y = 0
                    self.hand_fixed.put(shell, x, y)
                return

            hand = current.hand
            n = len(hand)
            total_w = max(CARD_W, (n - 1) * CARD_PEEK + CARD_W) if n else CARD_W
            self.hand_fixed.set_size_request(total_w, CARD_H + CARD_LIFT + 8)
            for idx, card in enumerate(hand):
                button = Gtk.ToggleButton()
                button.add_css_class("hand-card")
                button.set_active(idx in self.selected_hand_indexes)
                button.set_sensitive(True)
                button.set_child(build_card_widget(card, self.assets_root, format_card))
                button.connect("toggled", self._on_hand_toggled, idx)
                x = idx * CARD_PEEK
                y = 0 if idx in self.selected_hand_indexes else CARD_LIFT
                self.hand_fixed.put(button, x, y)

        def _refresh_melds(self) -> None:
            n_items = self.meld_model.get_n_items()
            if n_items > 0:
                self.meld_model.splice(0, n_items, [])
            self._meld_index_mapping = []  # Reset mapping
            viewer = self._viewer_player_id()
            for player_id, melds_box in (
                (PlayerId.NORTH, self.north_melds_box),
                (PlayerId.SOUTH, self.south_melds_box),
            ):
                self._clear_box(melds_box)
                player = self.engine.state.players[player_id]

                if player.red_threes:
                    frame = Gtk.Frame(label="Red 3s")
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                    row.set_margin_top(4)
                    row.set_margin_bottom(4)
                    row.set_margin_start(4)
                    row.set_margin_end(4)
                    for card in player.red_threes:
                        row.append(
                            build_card_widget(card, self.assets_root, format_card)
                        )
                    frame.set_child(row)
                    melds_box.append(frame)

                if not player.melds:
                    placeholder = Gtk.Label(label="(no melds)")
                    placeholder.set_margin_start(8)
                    placeholder.set_valign(Gtk.Align.CENTER)
                    melds_box.append(placeholder)

                # Sort melds by natural rank numerically
                sorted_melds = sorted(
                    enumerate(player.melds),
                    key=lambda x: rank_sort_key(x[1].natural_rank),
                )

                for original_idx, meld in sorted_melds:
                    if player_id == viewer:
                        self.meld_model.append(f"Meld {original_idx}")
                        self._meld_index_mapping.append(original_idx)
                    title = f"Meld {original_idx}"
                    if meld.is_canasta:
                        title += " (Canasta)"
                    frame = Gtk.Frame(label=title)
                    if meld.is_canasta and meld.cards:
                        # Reorganize cards: natural first, wild last
                        reorganized = reorganize_meld_cards(meld.cards)
                        wild_cards = [c for c in reorganized if c.is_wild()]

                        if wild_cards:
                            # Show natural cards with wild cards fanned below
                            layout = Gtk.Fixed()
                            layout.set_size_request(
                                CARD_W + (len(wild_cards) - 1) * MELD_PEEK + 20,
                                CARD_H * 2,
                            )

                            # Show first natural card (or placeholder)
                            natural_cards = [c for c in reorganized if not c.is_wild()]
                            if natural_cards:
                                layout.put(
                                    build_card_widget(
                                        natural_cards[0], self.assets_root, format_card
                                    ),
                                    0,
                                    0,
                                )

                            # Fan wild cards below and to the right
                            for wild_idx, wild_card in enumerate(wild_cards):
                                x = wild_idx * MELD_PEEK
                                y = CARD_H + 4
                                layout.put(
                                    build_card_widget(
                                        wild_card, self.assets_root, format_card
                                    ),
                                    x,
                                    y,
                                )

                            shell = Gtk.Box()
                            shell.add_css_class("canasta-card-shell")
                            shell.set_margin_top(4)
                            shell.set_margin_bottom(4)
                            shell.set_margin_start(4)
                            shell.set_margin_end(4)
                            shell.append(layout)
                            frame.set_child(shell)
                        else:
                            # All natural cards - show first one prominently
                            shell = Gtk.Box()
                            shell.add_css_class("canasta-card-shell")
                            shell.set_margin_top(4)
                            shell.set_margin_bottom(4)
                            shell.set_margin_start(4)
                            shell.set_margin_end(4)
                            shell.append(
                                build_card_widget(
                                    reorganized[0], self.assets_root, format_card
                                )
                            )
                            frame.set_child(shell)
                    else:
                        # Regular meld: reorganize so natural cards come first
                        reorganized = reorganize_meld_cards(meld.cards)
                        fan = build_fanned_cards(
                            reorganized, self.assets_root, format_card
                        )
                        fan.set_margin_top(4)
                        fan.set_margin_bottom(4)
                        fan.set_margin_start(4)
                        fan.set_margin_end(4)
                        frame.set_child(fan)
                    melds_box.append(frame)

            if (
                self.meld_model.get_n_items() > 0
                and self.meld_selector.get_selected() >= self.meld_model.get_n_items()
            ):
                self.meld_selector.set_selected(0)

        def _refresh_controls(self) -> None:
            state = self.engine.state
            selected = self._selected_indexes()
            viewer = state.players[self._viewer_player_id()]
            is_human_turn = self.controllers.get(state.current_player) is None
            preview_active = self._draw_preview_inserted_cards is not None
            has_current_melds = bool(viewer.melds)
            selected_cards = [
                viewer.hand[idx] for idx in selected if idx < len(viewer.hand)
            ]
            needs_meld_selector = any(card.is_wild() for card in selected_cards)
            self.draw_button.set_sensitive(
                state.winner is None
                and is_human_turn
                and not state.turn_drawn
                and not preview_active
            )
            self.pickup_button.set_sensitive(
                state.winner is None
                and is_human_turn
                and not state.turn_drawn
                and bool(selected)
                and not preview_active
            )
            self.meld_button.set_sensitive(
                state.winner is None
                and is_human_turn
                and state.turn_drawn
                and bool(selected)
                and not preview_active
            )
            self.add_button.set_sensitive(
                state.winner is None
                and is_human_turn
                and state.turn_drawn
                and bool(selected)
                and has_current_melds
                and not preview_active
            )
            self.discard_button.set_sensitive(
                state.winner is None
                and is_human_turn
                and state.turn_drawn
                and len(selected) == 1
                and not preview_active
            )
            self.deselect_all_button.set_sensitive(len(selected) > 1)
            self.next_round_button.set_sensitive(state.winner is not None)
            self.meld_selector.set_sensitive(
                is_human_turn
                and has_current_melds
                and needs_meld_selector
                and not preview_active
            )

        def _refresh(self) -> None:
            self._refresh_summary()
            self._refresh_hand()
            self._refresh_melds()
            self._refresh_controls()
            self._update_stats_display()

        def _run_action(self, callback) -> None:
            self._cancel_draw_preview()
            try:
                result = callback()
                self.selected_hand_indexes.clear()
                self._set_status(result.message)
            except RuleError as exc:
                self._set_status(f"error: {exc}")
            self._refresh()
            # Auto-save game state after each action
            save_game(self.engine.state)
            self._maybe_play_bot_turn()

        def _on_hand_toggled(self, button: Gtk.ToggleButton, index: int) -> None:
            if button.get_active():
                self.selected_hand_indexes.add(index)
            else:
                self.selected_hand_indexes.discard(index)
            self._refresh_summary()
            self._refresh_controls()

        def _on_deselect_all(self, _button: Gtk.Button) -> None:
            self.selected_hand_indexes.clear()
            self._refresh_hand()
            self._refresh_summary()
            self._refresh_controls()

        def _on_draw(self, _button: Gtk.Button) -> None:
            self._cancel_draw_preview()
            before_hand = list(self.engine.current_hand())
            try:
                result = self.engine.draw_stock()
                self.selected_hand_indexes.clear()
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
                self._draw_preview_base_hand = before_hand
                self._draw_preview_inserted_cards = inserted
                hadj = self.hand_scroll.get_hadjustment()
                self._draw_preview_restore_scroll = hadj.get_value()
                self._draw_preview_timeout_id = GLib.timeout_add(
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
                if dropdown_idx >= len(self._meld_index_mapping):
                    self._set_status("error: select a meld first")
                    self._refresh_controls()
                    return
                # Map dropdown index to actual meld index
                meld_idx = self._meld_index_mapping[dropdown_idx]

            self._run_action(lambda: self.engine.add_to_meld(meld_idx, indexes))

        def _on_discard(self, _button: Gtk.Button) -> None:
            indexes = self._selected_indexes()
            if len(indexes) != 1:
                self._set_status("error: select exactly one card to discard")
                self._refresh_controls()
                return
            self._run_action(lambda: self.engine.discard(indexes[0]))

        def _on_next_round(self, _button: Gtk.Button) -> None:
            self._last_winner = None  # Reset winner tracking when moving to next round
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
