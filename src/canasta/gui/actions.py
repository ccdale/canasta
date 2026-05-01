"""Turn action helpers for the Canasta GTK window."""

from __future__ import annotations

from canasta.gui.utilities import new_cards_in_hand, resolve_target_meld_index
from canasta.model import RuleError


def on_hand_toggled(window, button, index: int) -> None:
    """Update selected hand indexes when a card toggle changes."""
    if button.get_active():
        window.ui_state.selected_hand_indexes.add(index)
    else:
        window.ui_state.selected_hand_indexes.discard(index)
    window._refresh_summary()
    window._refresh_controls()


def on_deselect_all(window) -> None:
    """Clear all selected cards in the visible hand."""
    window.ui_state.selected_hand_indexes.clear()
    window._refresh_hand()
    window._refresh_summary()
    window._refresh_controls()


def on_draw(window, GLib) -> None:
    """Draw from stock and trigger the temporary inserted-card preview."""
    window._cancel_draw_preview()
    before_hand = list(window.engine.current_hand())
    try:
        result = window.engine.draw_stock()
        window.ui_state.selected_hand_indexes.clear()
        window._set_status(result.message)
    except RuleError as exc:
        window._set_status(f"error: {exc}")
        window._refresh()
        window.bot_runner.maybe_play_turn()
        return

    after_hand = list(window.engine.current_hand())
    inserted = new_cards_in_hand(before_hand, after_hand)
    if inserted:
        # Show newly inserted cards at draw/pickup position briefly.
        window.ui_state.draw_preview_base_hand = before_hand
        window.ui_state.draw_preview_inserted_cards = inserted
        hadj = window.hand_scroll.get_hadjustment()
        window.ui_state.draw_preview_restore_scroll = hadj.get_value()
        window.ui_state.draw_preview_timeout_id = GLib.timeout_add(
            1000, window._clear_draw_preview
        )

    window._refresh()
    if inserted:
        hadj = window.hand_scroll.get_hadjustment()
        hadj.set_value(max(0.0, hadj.get_upper() - hadj.get_page_size()))
    window.bot_runner.maybe_play_turn()


def on_pickup(window) -> None:
    """Attempt discard-pile pickup using the currently selected cards."""
    indexes = window._selected_indexes()
    window._run_action(lambda: window.engine.pickup_discard(indexes))


def on_meld(window) -> None:
    """Create a meld from the currently selected cards."""
    indexes = window._selected_indexes()
    window._run_action(lambda: window.engine.create_meld(indexes))


def on_add_to_meld(window) -> None:
    """Add selected cards to an existing meld, auto-resolving target where possible."""
    indexes = window._selected_indexes()
    current = window.engine.state.players[window.engine.state.current_player]
    cards = [current.hand[idx] for idx in indexes]
    try:
        meld_idx = resolve_target_meld_index(current.melds, cards)
    except RuleError as exc:
        window._set_status(f"error: {exc}")
        window._refresh_controls()
        return

    if meld_idx is None:
        dropdown_idx = window.meld_selector.get_selected()
        if dropdown_idx >= len(window.ui_state.meld_index_mapping):
            window._set_status("error: select a meld first")
            window._refresh_controls()
            return
        # Map dropdown index to actual meld index.
        meld_idx = window.ui_state.meld_index_mapping[dropdown_idx]

    window._run_action(lambda: window.engine.add_to_meld(meld_idx, indexes))


def on_discard(window) -> None:
    """Discard the selected card when exactly one card is selected."""
    indexes = window._selected_indexes()
    if len(indexes) != 1:
        window._set_status("error: select exactly one card to discard")
        window._refresh_controls()
        return
    window._run_action(lambda: window.engine.discard(indexes[0]))


def on_next_round(window) -> None:
    """Advance to the next round after a winner is set."""
    window.ui_state.last_winner = None
    window._run_action(window.engine.next_round)
