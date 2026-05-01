"""Turn action helpers for the Canasta GTK window."""

from __future__ import annotations

from canasta.gui.persistence import save_game
from canasta.gui.utilities import new_cards_in_hand, resolve_target_meld_index
from canasta.model import RuleError
from canasta.rules import discard_pile_is_frozen


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


def on_discard_pile_clicked(window) -> None:
    """Click on the discard pile: auto-select matching hand cards and attempt pickup.

    Frozen pile: requires exactly 2 natural cards matching the top discard rank.
    Unfrozen pile: selects all natural matching cards.

    On opening-meld shortfall, the auto-selection is kept in place and a hint is
    shown — the player adds more cards manually then presses Pickup.
    """
    state = window.engine.state
    is_human_turn = window.controllers.get(state.current_player) is None
    if not is_human_turn or state.turn_drawn or not state.discard or state.winner is not None:
        return

    top = state.discard[-1]
    if top.is_wild() or top.is_black_three():
        window._set_status(
            "Cannot pick up: pile is frozen with a wild card or black three on top"
        )
        return

    player = state.players[state.current_player]
    matching_indexes = [
        idx
        for idx, card in enumerate(player.hand)
        if card.rank == top.rank and not card.is_wild()
    ]

    frozen = discard_pile_is_frozen(state.discard)
    if frozen:
        if len(matching_indexes) < 2:
            window._set_status(
                f"Frozen pickup needs 2 natural {top.rank}s in hand "
                f"— you have {len(matching_indexes)}"
            )
            return
        auto_indexes = matching_indexes[:2]
    else:
        if not matching_indexes:
            window._set_status(f"No {top.rank}s in hand to pick up discard pile")
            return
        auto_indexes = matching_indexes

    # Apply auto-selection and attempt pickup immediately.
    window.ui_state.selected_hand_indexes.clear()
    window.ui_state.selected_hand_indexes.update(auto_indexes)
    window._cancel_draw_preview()

    try:
        result = window.engine.pickup_discard(auto_indexes)
        window.ui_state.selected_hand_indexes.clear()
        window._set_status(result.message)
        window._refresh()
        save_game(window.engine.state)
        window.bot_runner.maybe_play_turn()
    except RuleError as exc:
        msg = str(exc)
        if "opening meld" in msg:
            # Leave selection in place so the player can add more cards and press Pickup.
            window._set_status(
                f"Opening meld needs 50+ pts — {len(auto_indexes)} {top.rank}"
                f"{'s' if len(auto_indexes) != 1 else ''} selected. "
                "Add more cards, then press Pickup."
            )
            window._refresh()
        else:
            window.ui_state.selected_hand_indexes.clear()
            window._set_status(f"error: {exc}")
            window._refresh()
