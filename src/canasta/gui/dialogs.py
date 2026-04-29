"""Modal dialog classes for the Canasta GUI."""

from __future__ import annotations

from typing import Callable

from canasta.gui.persistence import has_saved_game


def create_resume_game_dialog(
    parent_window,
    on_resume: Callable[[], None],
    on_new_game: Callable[[], None],
) -> None:
    """Create and present a modal dialog asking to resume or start a new game.

    Args:
        parent_window: The parent GTK window (makes this dialog modal to it)
        on_resume: Callback when user chooses to resume saved game
        on_new_game: Callback when user chooses to start new game
    """
    # Import GTK here to avoid requiring it at module level
    from gi.repository import Gtk  # pylint: disable=import-outside-toplevel

    if not has_saved_game():
        return

    dialog = Gtk.Window()
    dialog.set_title("Resume Game?")
    dialog.set_transient_for(parent_window)
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
    new_btn.connect("clicked", lambda _: (dialog.close(), on_new_game()))
    btn_row.append(new_btn)

    resume_btn = Gtk.Button(label="Resume")
    resume_btn.add_css_class("suggested-action")
    resume_btn.connect("clicked", lambda _: (dialog.close(), on_resume()))
    btn_row.append(resume_btn)

    box.append(btn_row)

    # Defer dialog presentation until after main window is realized
    from gi.repository import GLib  # pylint: disable=import-outside-toplevel

    GLib.idle_add(lambda: dialog.present() or False)


def create_new_game_dialog(
    parent_window,
    north_choice: str,
    south_choice: str,
    bot_seed: int,
    bot_choices: list[str],
    on_start: Callable[[str, str, int], None],
) -> None:
    """Create and present a new game configuration dialog.

    Args:
        parent_window: The parent GTK window (makes this dialog modal to it)
        north_choice: Current north player choice
        south_choice: Current south player choice
        bot_seed: Current bot seed value
        bot_choices: List of available bot choices
        on_start: Callback when user clicks Start with (north, south, seed)
    """
    # Import GTK here to avoid requiring it at module level
    from gi.repository import Gtk  # pylint: disable=import-outside-toplevel

    dialog = Gtk.Window()
    dialog.set_title("New Game")
    dialog.set_transient_for(parent_window)
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
    north_model = Gtk.StringList.new(bot_choices)
    north_dd = Gtk.DropDown.new(north_model, None)
    north_dd.set_selected(bot_choices.index(north_choice))
    north_row.append(north_dd)
    box.append(north_row)

    south_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    south_lbl = Gtk.Label(label="South seat:", xalign=0)
    south_lbl.set_hexpand(True)
    south_row.append(south_lbl)
    south_model = Gtk.StringList.new(bot_choices)
    south_dd = Gtk.DropDown.new(south_model, None)
    south_dd.set_selected(bot_choices.index(south_choice))
    south_row.append(south_dd)
    box.append(south_row)

    seed_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    seed_lbl = Gtk.Label(label="Bot seed:", xalign=0)
    seed_lbl.set_hexpand(True)
    seed_row.append(seed_lbl)
    adj = Gtk.Adjustment.new(bot_seed, 0, 9999, 1, 10, 0)
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
        north = bot_choices[north_dd.get_selected()]
        south = bot_choices[south_dd.get_selected()]
        seed = int(seed_spin.get_value())
        dialog.close()
        on_start(north, south, seed)

    start_btn.connect("clicked", _on_start)
    btn_row.append(start_btn)
    box.append(btn_row)

    dialog.present()
