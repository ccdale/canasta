"""Rendering helpers for the Canasta GTK UI."""

from __future__ import annotations

from canasta.card_assets import back_image_path, card_image_path
from canasta.gui.utilities import format_card, rank_sort_key, reorganize_meld_cards
from canasta.gui.widgets import (
    CARD_H,
    CARD_LIFT,
    CARD_PEEK,
    CARD_W,
    MELD_PEEK,
    build_card_widget,
    build_fanned_cards,
    build_pile_picture,
)
from canasta.model import PlayerId
from canasta.rules import discard_pile_is_frozen

Gtk = None


def set_gtk_imports(gtk) -> None:
    """Set the deferred GTK import for renderer widgets."""
    global Gtk
    Gtk = gtk


class GameRenderer:
    """Encapsulate refresh and rendering logic for the main game window."""

    def __init__(self, window) -> None:
        self.window = window

    def refresh_summary(self) -> None:
        state = self.window.engine.state

        if (
            state.winner is not None
            and state.winner != self.window.ui_state.last_winner
        ):
            self.window.ui_state.last_winner = state.winner
            if state.winner == PlayerId.NORTH:
                self.window.north_wins += 1
            else:
                self.window.south_wins += 1
            from canasta.gui.persistence import save_game_stats

            save_game_stats(self.window.north_wins, self.window.south_wins)

        north = state.players[PlayerId.NORTH]
        self.window.north_melds_hdr.set_text(
            f"North  ({len(north.hand)} cards in hand)"
        )

        self.window.info_label.set_text(
            "\n".join(
                [
                    f"Round {state.round_number}  |  "
                    f"Current: {state.current_player.value}  |  "
                    + (
                        f"Winner: {state.winner.value}"
                        if state.winner is not None
                        else "No winner yet"
                    ),
                    f"Selected: {self.window._selected_indexes() or '(none)'}  |  "
                    f"Frozen: {discard_pile_is_frozen(state.discard)}  |  "
                    f"Turn drawn: {state.turn_drawn}  |  "
                    f"Hand: {len(state.players[self.window._viewer_player_id()].hand)} cards",
                ]
            )
        )

        north_round = self.window.engine.score(PlayerId.NORTH)
        south_round = self.window.engine.score(PlayerId.SOUTH)
        north_total = self.window.engine.total_score(PlayerId.NORTH)
        south_total = self.window.engine.total_score(PlayerId.SOUTH)
        self.window.score_label.set_text(
            f"North: {north_round} pts (total {north_total})  |  "
            f"South: {south_round} pts (total {south_total})"
        )

        self.window._clear_box(self.window.stock_box)
        stock_title = Gtk.Label(label=f"Stock ({len(state.stock)})")
        stock_title.add_css_class("section-label")
        self.window.stock_box.append(stock_title)
        back_path = back_image_path(self.window.assets_root)
        if back_path is not None:
            self.window.stock_box.append(build_pile_picture(back_path))
        else:
            self.window.stock_box.append(Gtk.Label(label="[stock]"))

        self.window._clear_box(self.window.discard_box)
        discard_title = Gtk.Label(
            label=f"Discard ({len(state.discard)})"
            + (" \u2744" if discard_pile_is_frozen(state.discard) else "")
        )
        discard_title.add_css_class("section-label")
        self.window.discard_box.append(discard_title)
        if state.discard:
            top_discard = state.discard[-1]
            top_discard_path = card_image_path(top_discard, self.window.assets_root)
            if top_discard_path is not None:
                self.window.discard_box.append(build_pile_picture(top_discard_path))
            else:
                self.window.discard_box.append(
                    build_card_widget(top_discard, self.window.assets_root, format_card)
                )
        else:
            self.window.discard_box.append(Gtk.Label(label="(empty)"))

    def refresh_hand(self) -> None:
        self.window._clear_box(self.window.hand_fixed)
        current = self.window.engine.state.players[self.window._viewer_player_id()]
        preview_active = (
            self.window.ui_state.draw_preview_base_hand is not None
            and self.window.ui_state.draw_preview_inserted_cards is not None
        )

        if preview_active:
            base_hand = self.window.ui_state.draw_preview_base_hand or []
            inserted_cards = self.window.ui_state.draw_preview_inserted_cards or []
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
            self.window.hand_fixed.set_size_request(total_w, CARD_H + CARD_LIFT + 8)

            for idx, card in enumerate(base_hand):
                shell = Gtk.Box()
                shell.add_css_class("hand-card")
                shell.append(
                    build_card_widget(card, self.window.assets_root, format_card)
                )
                x = idx * CARD_PEEK
                y = CARD_LIFT
                self.window.hand_fixed.put(shell, x, y)

            start_x = base_w + inserted_gap
            for idx, card in enumerate(inserted_cards):
                shell = Gtk.Box()
                shell.add_css_class("hand-card")
                shell.add_css_class("draw-preview-new")
                shell.append(
                    build_card_widget(card, self.window.assets_root, format_card)
                )
                x = start_x + idx * inserted_stride
                y = 0
                self.window.hand_fixed.put(shell, x, y)
            return

        hand = current.hand
        n = len(hand)
        total_w = max(CARD_W, (n - 1) * CARD_PEEK + CARD_W) if n else CARD_W
        self.window.hand_fixed.set_size_request(total_w, CARD_H + CARD_LIFT + 8)
        for idx, card in enumerate(hand):
            button = Gtk.ToggleButton()
            button.add_css_class("hand-card")
            button.set_active(idx in self.window.ui_state.selected_hand_indexes)
            button.set_sensitive(True)
            button.set_child(
                build_card_widget(card, self.window.assets_root, format_card)
            )
            button.connect("toggled", self.window._on_hand_toggled, idx)
            x = idx * CARD_PEEK
            y = 0 if idx in self.window.ui_state.selected_hand_indexes else CARD_LIFT
            self.window.hand_fixed.put(button, x, y)

    def refresh_melds(self) -> None:
        n_items = self.window.meld_model.get_n_items()
        if n_items > 0:
            self.window.meld_model.splice(0, n_items, [])
        self.window.ui_state.meld_index_mapping = []
        viewer = self.window._viewer_player_id()
        for player_id, melds_box in (
            (PlayerId.NORTH, self.window.north_melds_box),
            (PlayerId.SOUTH, self.window.south_melds_box),
        ):
            self.window._clear_box(melds_box)
            player = self.window.engine.state.players[player_id]

            if player.red_threes:
                frame = Gtk.Frame(label="Red 3s")
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                row.set_margin_top(4)
                row.set_margin_bottom(4)
                row.set_margin_start(4)
                row.set_margin_end(4)
                for card in player.red_threes:
                    row.append(
                        build_card_widget(card, self.window.assets_root, format_card)
                    )
                frame.set_child(row)
                melds_box.append(frame)

            if not player.melds:
                placeholder = Gtk.Label(label="(no melds)")
                placeholder.set_margin_start(8)
                placeholder.set_valign(Gtk.Align.CENTER)
                melds_box.append(placeholder)

            sorted_melds = sorted(
                enumerate(player.melds),
                key=lambda item: rank_sort_key(item[1].natural_rank),
            )

            for original_idx, meld in sorted_melds:
                if player_id == viewer:
                    self.window.meld_model.append(f"Meld {original_idx}")
                    self.window.ui_state.meld_index_mapping.append(original_idx)
                title = f"Meld {original_idx}"
                if meld.is_canasta:
                    title += " (Canasta)"
                frame = Gtk.Frame(label=title)
                if meld.is_canasta and meld.cards:
                    reorganized = reorganize_meld_cards(meld.cards)
                    wild_cards = [card for card in reorganized if card.is_wild()]

                    if wild_cards:
                        layout = Gtk.Fixed()
                        layout.set_size_request(
                            CARD_W + (len(wild_cards) - 1) * MELD_PEEK + 20,
                            CARD_H * 2,
                        )

                        natural_cards = [
                            card for card in reorganized if not card.is_wild()
                        ]
                        if natural_cards:
                            layout.put(
                                build_card_widget(
                                    natural_cards[0],
                                    self.window.assets_root,
                                    format_card,
                                ),
                                0,
                                0,
                            )

                        for wild_idx, wild_card in enumerate(wild_cards):
                            x = wild_idx * MELD_PEEK
                            y = CARD_H + 4
                            layout.put(
                                build_card_widget(
                                    wild_card, self.window.assets_root, format_card
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
                        shell = Gtk.Box()
                        shell.add_css_class("canasta-card-shell")
                        shell.set_margin_top(4)
                        shell.set_margin_bottom(4)
                        shell.set_margin_start(4)
                        shell.set_margin_end(4)
                        shell.append(
                            build_card_widget(
                                reorganized[0], self.window.assets_root, format_card
                            )
                        )
                        frame.set_child(shell)
                else:
                    reorganized = reorganize_meld_cards(meld.cards)
                    fan = build_fanned_cards(
                        reorganized, self.window.assets_root, format_card
                    )
                    fan.set_margin_top(4)
                    fan.set_margin_bottom(4)
                    fan.set_margin_start(4)
                    fan.set_margin_end(4)
                    frame.set_child(fan)
                melds_box.append(frame)

        if (
            self.window.meld_model.get_n_items() > 0
            and self.window.meld_selector.get_selected()
            >= self.window.meld_model.get_n_items()
        ):
            self.window.meld_selector.set_selected(0)

    def refresh_controls(self) -> None:
        state = self.window.engine.state
        selected = self.window._selected_indexes()
        viewer = state.players[self.window._viewer_player_id()]
        is_human_turn = self.window.controllers.get(state.current_player) is None
        preview_active = self.window.ui_state.draw_preview_inserted_cards is not None
        has_current_melds = bool(viewer.melds)
        selected_cards = [
            viewer.hand[idx] for idx in selected if idx < len(viewer.hand)
        ]
        needs_meld_selector = any(card.is_wild() for card in selected_cards)
        self.window.draw_button.set_sensitive(
            state.winner is None
            and is_human_turn
            and not state.turn_drawn
            and not preview_active
        )
        self.window.pickup_button.set_sensitive(
            state.winner is None
            and is_human_turn
            and not state.turn_drawn
            and bool(selected)
            and not preview_active
        )
        self.window.meld_button.set_sensitive(
            state.winner is None
            and is_human_turn
            and state.turn_drawn
            and bool(selected)
            and not preview_active
        )
        self.window.add_button.set_sensitive(
            state.winner is None
            and is_human_turn
            and state.turn_drawn
            and bool(selected)
            and has_current_melds
            and not preview_active
        )
        self.window.discard_button.set_sensitive(
            state.winner is None
            and is_human_turn
            and state.turn_drawn
            and len(selected) == 1
            and not preview_active
        )
        self.window.deselect_all_button.set_sensitive(len(selected) > 1)
        self.window.next_round_button.set_sensitive(state.winner is not None)
        self.window.meld_selector.set_sensitive(
            is_human_turn
            and has_current_melds
            and needs_meld_selector
            and not preview_active
        )

    def refresh(self) -> None:
        self.refresh_summary()
        self.refresh_hand()
        self.refresh_melds()
        self.refresh_controls()
        self.window._update_stats_display()
