"""Layout construction helpers for the Canasta GTK window."""

from __future__ import annotations

from canasta.gui.widgets import CARD_H, CARD_LIFT, CARD_W


def build_game_layout(window, Gtk) -> None:
    """Create and attach all top-level GUI widgets for the game window."""
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    root.set_margin_top(8)
    root.set_margin_bottom(8)
    root.set_margin_start(8)
    root.set_margin_end(8)
    window.set_child(root)

    # Row 1: North melds
    window.north_melds_hdr = Gtk.Label(label="North melds", xalign=0)
    window.north_melds_hdr.add_css_class("section-label")
    root.append(window.north_melds_hdr)
    north_melds_scroll = Gtk.ScrolledWindow()
    north_melds_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
    north_melds_scroll.set_min_content_height(CARD_H + 24)
    root.append(north_melds_scroll)
    window.north_melds_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    window.north_melds_box.set_margin_top(4)
    window.north_melds_box.set_margin_bottom(4)
    window.north_melds_box.set_margin_start(6)
    north_melds_scroll.set_child(window.north_melds_box)

    root.append(Gtk.Separator())

    # Row 2: Stock and discard
    pile_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    pile_row.set_margin_start(6)
    pile_row.set_size_request(-1, CARD_H + 34)
    pile_row.set_valign(Gtk.Align.START)
    pile_row.set_vexpand(False)
    root.append(pile_row)

    window.stock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    window.stock_box.set_size_request(CARD_W + 4, CARD_H + 28)
    window.stock_box.set_valign(Gtk.Align.START)
    window.stock_box.set_vexpand(False)
    pile_row.append(window.stock_box)

    window.discard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    window.discard_box.set_size_request(CARD_W + 4, CARD_H + 28)
    window.discard_box.set_valign(Gtk.Align.START)
    window.discard_box.set_vexpand(False)
    pile_row.append(window.discard_box)

    # Row 3: Controls
    controls_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    controls_row.set_margin_start(6)
    root.append(controls_row)

    window.draw_button = Gtk.Button(label="Draw")
    window.draw_button.connect("clicked", window._on_draw)
    controls_row.append(window.draw_button)

    window.pickup_button = Gtk.Button(label="Pickup")
    window.pickup_button.connect("clicked", window._on_pickup)
    controls_row.append(window.pickup_button)

    window.meld_button = Gtk.Button(label="Meld")
    window.meld_button.connect("clicked", window._on_meld)
    controls_row.append(window.meld_button)

    window.add_button = Gtk.Button(label="Add to Meld")
    window.add_button.connect("clicked", window._on_add_to_meld)
    controls_row.append(window.add_button)

    window.discard_button = Gtk.Button(label="Discard")
    window.discard_button.connect("clicked", window._on_discard)
    controls_row.append(window.discard_button)

    window.deselect_all_button = Gtk.Button(label="Deselect All")
    window.deselect_all_button.connect("clicked", window._on_deselect_all)
    controls_row.append(window.deselect_all_button)

    window.next_round_button = Gtk.Button(label="Next Round")
    window.next_round_button.connect("clicked", window._on_next_round)
    controls_row.append(window.next_round_button)

    window.meld_model = Gtk.StringList.new([])
    window.meld_selector = Gtk.DropDown.new(window.meld_model, None)
    controls_row.append(window.meld_selector)

    new_game_button = Gtk.Button(label="New Game...")
    new_game_button.connect("clicked", window._show_new_game_dialog)
    controls_row.append(new_game_button)

    # Row 4: Status
    window.info_label = Gtk.Label(xalign=0)
    window.info_label.set_wrap(True)
    window.info_label.set_margin_start(6)
    root.append(window.info_label)

    window.score_label = Gtk.Label(xalign=0)
    window.score_label.set_wrap(True)
    window.score_label.set_margin_start(6)
    root.append(window.score_label)

    window.status_label = Gtk.Label(xalign=0)
    window.status_label.set_wrap(True)
    window.status_label.set_margin_start(6)
    root.append(window.status_label)

    window.stats_label = Gtk.Label(xalign=0)
    window.stats_label.set_wrap(True)
    window.stats_label.set_margin_start(6)
    root.append(window.stats_label)

    root.append(Gtk.Separator())

    # Row 5: South hand
    hand_hdr = Gtk.Label(label="Your hand", xalign=0)
    hand_hdr.add_css_class("section-label")
    hand_hdr.set_margin_start(6)
    root.append(hand_hdr)
    hand_scroll = Gtk.ScrolledWindow()
    hand_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
    hand_scroll.set_min_content_height(CARD_H + CARD_LIFT + 8)
    root.append(hand_scroll)
    window.hand_scroll = hand_scroll
    window.hand_fixed = Gtk.Fixed()
    hand_scroll.set_child(window.hand_fixed)

    root.append(Gtk.Separator())

    # Row 6: South melds
    south_melds_hdr = Gtk.Label(label="South melds", xalign=0)
    south_melds_hdr.add_css_class("section-label")
    south_melds_hdr.set_margin_start(6)
    root.append(south_melds_hdr)
    south_melds_scroll = Gtk.ScrolledWindow()
    south_melds_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
    south_melds_scroll.set_min_content_height(CARD_H + 24)
    root.append(south_melds_scroll)
    window.south_melds_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    window.south_melds_box.set_margin_top(4)
    window.south_melds_box.set_margin_bottom(4)
    window.south_melds_box.set_margin_start(6)
    south_melds_scroll.set_child(window.south_melds_box)
