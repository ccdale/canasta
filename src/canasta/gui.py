from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from canasta.bot_strategies import TurnBot
from canasta.bots import BotKind, build_bot, play_bot_turn
from canasta.card_assets import asset_dir, back_image_path, card_image_path
from canasta.engine import CanastaEngine
from canasta.model import Card, PlayerId, RuleError
from canasta.rules import discard_pile_is_frozen

# Card widget dimensions — proportional to the natural 537×750 px source images,
# matching the ratio used in patience/ui/cards.py.
CARD_W = 90
CARD_H = 126

_BOT_CHOICES = ["human", "random", "greedy", "safe", "aggro", "planner"]

# Green-felt table CSS matching patience/ui/theme.py style.
_TABLE_CSS = b"""
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
"""


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canasta GTK4 GUI")
    parser.add_argument(
        "--assets-dir",
        default=None,
        help="Override card image directory (defaults to XDG data dir or CANASTA_CARD_ASSET_DIR)",
    )
    parser.add_argument(
        "--north",
        choices=_BOT_CHOICES,
        default="human",
        help="Controller for the north seat (default: human)",
    )
    parser.add_argument(
        "--south",
        choices=_BOT_CHOICES,
        default="human",
        help="Controller for the south seat (default: human)",
    )
    parser.add_argument("--bot-seed", type=int, default=0)
    return parser.parse_args(argv)


def _python_candidates() -> list[str]:
    candidates = [
        shutil.which("python3"),
        "/usr/bin/python3",
        "/sbin/python3.14",
    ]
    ordered: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in ordered:
            ordered.append(candidate)
    return ordered


def _find_python_with_gtk() -> str | None:
    check = "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk"
    for candidate in _python_candidates():
        result = subprocess.run(
            [candidate, "-c", check],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            return candidate
    return None


def _reexec_with_system_python(argv: list[str]) -> int | None:
    if os.environ.get("CANASTA_GUI_SYSTEM_PYTHON") == "1":
        return None
    candidate = _find_python_with_gtk()
    if candidate is None:
        return None

    env = dict(os.environ)
    env["CANASTA_GUI_SYSTEM_PYTHON"] = "1"
    source_root = Path(__file__).resolve().parents[1]
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{source_root}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(source_root)
    )
    result = subprocess.run(
        [candidate, "-m", "canasta.gui", *argv],
        env=env,
        check=False,
    )
    return result.returncode


def _format_card(card: Card) -> str:
    if card.rank == "JOKER":
        return "JOKER"
    return f"{card.rank}{card.suit}"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        import gi

        gi.require_version("Gdk", "4.0")
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gdk, Gio, Gtk
    except ModuleNotFoundError:
        exit_code = _reexec_with_system_python(argv or sys.argv[1:])
        if exit_code is not None:
            return exit_code
        print(
            "GTK4 GUI requires PyGObject (gi). Install python3-gi or pygobject, "
            "or launch with a system Python that provides GTK4 bindings.",
            file=sys.stderr,
        )
        return 1

    def _install_css() -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        provider = Gtk.CssProvider()
        provider.load_from_data(_TABLE_CSS)
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_card_picture(image_path: Path) -> Gtk.Picture:
        picture = Gtk.Picture.new_for_filename(str(image_path))
        picture.set_size_request(CARD_W, CARD_H)
        picture.set_content_fit(Gtk.ContentFit.FILL)
        return picture

    def _build_card_widget(card: Card, assets_root: Path) -> Gtk.Widget:
        path = card_image_path(card, assets_root)
        if path is not None:
            return _build_card_picture(path)
        fallback = Gtk.Box()
        fallback.set_size_request(CARD_W, CARD_H)
        label = Gtk.Label(label=_format_card(card))
        label.set_wrap(True)
        fallback.append(label)
        return fallback

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
            self.set_title("Canasta")
            self.set_default_size(1280, 900)
            self.add_css_class("table-window")

            self.engine = CanastaEngine()
            self.controllers = _build_controllers(args)
            self.selected_hand_indexes: set[int] = set()
            self.assets_root = (
                Path(args.assets_dir).expanduser() if args.assets_dir else asset_dir()
            )

            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            root.set_margin_top(12)
            root.set_margin_bottom(12)
            root.set_margin_start(12)
            root.set_margin_end(12)
            self.set_child(root)

            self.info_label = Gtk.Label(xalign=0)
            self.info_label.set_wrap(True)
            root.append(self.info_label)

            self.status_label = Gtk.Label(xalign=0)
            self.status_label.set_wrap(True)
            root.append(self.status_label)

            summary = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
            root.append(summary)

            self.stock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            summary.append(self.stock_box)

            self.discard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            summary.append(self.discard_box)

            self.score_label = Gtk.Label(xalign=0)
            self.score_label.set_wrap(True)
            summary.append(self.score_label)

            controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            root.append(controls)

            self.draw_button = Gtk.Button(label="Draw")
            self.draw_button.connect("clicked", self._on_draw)
            controls.append(self.draw_button)

            self.pickup_button = Gtk.Button(label="Pickup Selected")
            self.pickup_button.connect("clicked", self._on_pickup)
            controls.append(self.pickup_button)

            self.meld_button = Gtk.Button(label="Meld Selected")
            self.meld_button.connect("clicked", self._on_meld)
            controls.append(self.meld_button)

            self.add_button = Gtk.Button(label="Add To Meld")
            self.add_button.connect("clicked", self._on_add_to_meld)
            controls.append(self.add_button)

            self.discard_button = Gtk.Button(label="Discard Selected")
            self.discard_button.connect("clicked", self._on_discard)
            controls.append(self.discard_button)

            self.next_round_button = Gtk.Button(label="Next Round")
            self.next_round_button.connect("clicked", self._on_next_round)
            controls.append(self.next_round_button)

            self.meld_selector = Gtk.ComboBoxText()
            controls.append(self.meld_selector)

            hand_title = Gtk.Label(label="Current hand", xalign=0)
            root.append(hand_title)

            hand_scroll = Gtk.ScrolledWindow()
            hand_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
            hand_scroll.set_min_content_height(180)
            root.append(hand_scroll)

            self.hand_flow = Gtk.FlowBox()
            self.hand_flow.set_selection_mode(Gtk.SelectionMode.NONE)
            self.hand_flow.set_max_children_per_line(8)
            self.hand_flow.set_row_spacing(8)
            self.hand_flow.set_column_spacing(8)
            hand_scroll.set_child(self.hand_flow)

            melds_title = Gtk.Label(label="Melds", xalign=0)
            root.append(melds_title)

            melds_scroll = Gtk.ScrolledWindow()
            melds_scroll.set_min_content_height(320)
            root.append(melds_scroll)

            self.melds_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            melds_scroll.set_child(self.melds_box)

            self._set_status(self._initial_status_message(args))
            self._refresh()

        def _maybe_play_bot_turn(self) -> None:
            """If the current player is bot-controlled, auto-play their full turn."""
            state = self.engine.state
            if state.winner is not None:
                return
            controller = self.controllers.get(state.current_player)
            if controller is None:
                return
            try:
                actions = play_bot_turn(self.engine, controller)
                self._set_status(
                    f"[{state.current_player.value}:{controller.name}] "
                    + " | ".join(actions)
                )
            except RuleError as exc:
                self._set_status(
                    f"[{state.current_player.value}:{controller.name}] error: {exc}"
                )
            self._refresh()
            # Chain: if the next player is also a bot, auto-play them too.
            self._maybe_play_bot_turn()

        def _initial_status_message(self, args: argparse.Namespace) -> str:
            if not self.assets_root.exists():
                return (
                    f"Card images not found at {self.assets_root}. "
                    "Using text fallback. Symlink ~/.local/share/canasta to your card images."
                )
            controllers_desc = f"north={args.north}  south={args.south}"
            return f"Assets: {self.assets_root}  |  {controllers_desc}"

        def _clear_box(self, box: Gtk.Widget) -> None:
            child = box.get_first_child()
            while child is not None:
                next_child = child.get_next_sibling()
                box.remove(child)
                child = next_child

        def _set_status(self, message: str) -> None:
            self.status_label.set_text(message)

        def _selected_indexes(self) -> list[int]:
            return sorted(self.selected_hand_indexes)

        def _render_card_widget(self, card: Card, caption: str) -> Gtk.Widget:
            wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            wrapper.append(_build_card_widget(card, self.assets_root))
            label = Gtk.Label(label=caption)
            wrapper.append(label)
            return wrapper

        def _refresh_summary(self) -> None:
            state = self.engine.state
            current = state.players[state.current_player]

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
                        f"Frozen discard: {discard_pile_is_frozen(state.discard)}  |  "
                        f"Turn drawn: {state.turn_drawn}  |  "
                        f"Hand: {len(current.hand)} cards",
                    ]
                )
            )

            north_round = self.engine.score(PlayerId.NORTH)
            south_round = self.engine.score(PlayerId.SOUTH)
            north_total = self.engine.total_score(PlayerId.NORTH)
            south_total = self.engine.total_score(PlayerId.SOUTH)
            self.score_label.set_text(
                "\n".join(
                    [
                        f"North round score: {north_round}",
                        f"South round score: {south_round}",
                        f"North total score: {north_total}",
                        f"South total score: {south_total}",
                    ]
                )
            )

            self._clear_box(self.stock_box)
            stock_title = Gtk.Label(label=f"Stock ({len(state.stock)})")
            stock_title.add_css_class("section-label")
            self.stock_box.append(stock_title)
            back_path = back_image_path(self.assets_root)
            if back_path is not None:
                self.stock_box.append(_build_card_picture(back_path))
            else:
                self.stock_box.append(Gtk.Label(label="[stock]"))

            self._clear_box(self.discard_box)
            discard_title = Gtk.Label(label=f"Discard ({len(state.discard)})")
            discard_title.add_css_class("section-label")
            self.discard_box.append(discard_title)
            top_discard = state.discard[-1]
            self.discard_box.append(
                self._render_card_widget(top_discard, _format_card(top_discard))
            )

        def _refresh_hand(self) -> None:
            self._clear_box(self.hand_flow)
            current = self.engine.state.players[self.engine.state.current_player]
            for idx, card in enumerate(current.hand):
                button = Gtk.ToggleButton()
                button.set_active(idx in self.selected_hand_indexes)
                button.set_child(
                    self._render_card_widget(card, f"{idx}: {_format_card(card)}")
                )
                button.connect("toggled", self._on_hand_toggled, idx)
                self.hand_flow.insert(button, -1)

        def _refresh_melds(self) -> None:
            self._clear_box(self.melds_box)
            self.meld_selector.remove_all()
            for player_id in (PlayerId.NORTH, PlayerId.SOUTH):
                player = self.engine.state.players[player_id]
                section = Gtk.Frame(label=f"{player_id.value.title()} melds")
                inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                inner.set_margin_top(8)
                inner.set_margin_bottom(8)
                inner.set_margin_start(8)
                inner.set_margin_end(8)

                if player.red_threes:
                    red_threes = Gtk.Box(
                        orientation=Gtk.Orientation.HORIZONTAL, spacing=6
                    )
                    for card in player.red_threes:
                        red_threes.append(
                            self._render_card_widget(card, _format_card(card))
                        )
                    inner.append(Gtk.Label(label="Red threes", xalign=0))
                    inner.append(red_threes)

                if not player.melds:
                    inner.append(Gtk.Label(label="(none)", xalign=0))
                for idx, meld in enumerate(player.melds):
                    if player_id == self.engine.state.current_player:
                        self.meld_selector.append(str(idx), f"Meld {idx}")
                    meld_row = Gtk.Box(
                        orientation=Gtk.Orientation.HORIZONTAL, spacing=6
                    )
                    meld_row.append(Gtk.Label(label=f"Meld {idx}", xalign=0))
                    for card in meld.cards:
                        meld_row.append(
                            self._render_card_widget(card, _format_card(card))
                        )
                    inner.append(meld_row)

                section.set_child(inner)
                self.melds_box.append(section)
            if self.meld_selector.get_active_id() is None:
                self.meld_selector.set_active(0)

        def _refresh_controls(self) -> None:
            state = self.engine.state
            selected = self._selected_indexes()
            current = state.players[state.current_player]
            has_current_melds = bool(current.melds)
            self.draw_button.set_sensitive(
                state.winner is None and not state.turn_drawn
            )
            self.pickup_button.set_sensitive(
                state.winner is None and not state.turn_drawn and bool(selected)
            )
            self.meld_button.set_sensitive(
                state.winner is None and state.turn_drawn and bool(selected)
            )
            self.add_button.set_sensitive(
                state.winner is None
                and state.turn_drawn
                and bool(selected)
                and has_current_melds
            )
            self.discard_button.set_sensitive(
                state.winner is None and state.turn_drawn and len(selected) == 1
            )
            self.next_round_button.set_sensitive(state.winner is not None)
            self.meld_selector.set_sensitive(has_current_melds)

        def _refresh(self) -> None:
            self._refresh_summary()
            self._refresh_hand()
            self._refresh_melds()
            self._refresh_controls()

        def _run_action(self, callback) -> None:
            try:
                result = callback()
                self.selected_hand_indexes.clear()
                self._set_status(result.message)
            except RuleError as exc:
                self._set_status(f"error: {exc}")
            self._refresh()
            self._maybe_play_bot_turn()

        def _on_hand_toggled(self, button: Gtk.ToggleButton, index: int) -> None:
            if button.get_active():
                self.selected_hand_indexes.add(index)
            else:
                self.selected_hand_indexes.discard(index)
            self._refresh_summary()
            self._refresh_controls()

        def _on_draw(self, _button: Gtk.Button) -> None:
            self._run_action(self.engine.draw_stock)

        def _on_pickup(self, _button: Gtk.Button) -> None:
            indexes = self._selected_indexes()
            self._run_action(lambda: self.engine.pickup_discard(indexes))

        def _on_meld(self, _button: Gtk.Button) -> None:
            indexes = self._selected_indexes()
            self._run_action(lambda: self.engine.create_meld(indexes))

        def _on_add_to_meld(self, _button: Gtk.Button) -> None:
            meld_id = self.meld_selector.get_active_id()
            if meld_id is None:
                self._set_status("error: select a meld first")
                return
            indexes = self._selected_indexes()
            self._run_action(lambda: self.engine.add_to_meld(int(meld_id), indexes))

        def _on_discard(self, _button: Gtk.Button) -> None:
            indexes = self._selected_indexes()
            if len(indexes) != 1:
                self._set_status("error: select exactly one card to discard")
                self._refresh_controls()
                return
            self._run_action(lambda: self.engine.discard(indexes[0]))

        def _on_next_round(self, _button: Gtk.Button) -> None:
            self._run_action(self.engine.next_round)

    class CanastaApplication(Gtk.Application):
        def __init__(self, args: argparse.Namespace) -> None:
            super().__init__(
                application_id="org.canasta.gtk", flags=Gio.ApplicationFlags.FLAGS_NONE
            )
            self.args = args

        def do_activate(self) -> None:
            _install_css()
            window = self.props.active_window
            if window is None:
                window = CanastaWindow(self, self.args)
            window.present()

    app = CanastaApplication(args)
    return app.run([])


if __name__ == "__main__":
    raise SystemExit(main())
