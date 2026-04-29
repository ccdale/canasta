"""UI state management for the Canasta GUI.

Groups all transient UI state variables for cleaner CanastaWindow initialization
and easier state management.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from canasta.model import Card, PlayerId


@dataclass
class UIState:
    """Encapsulates all transient UI state for the game window."""

    # Hand selection and meld display
    selected_hand_indexes: set[int] = field(default_factory=set)
    meld_index_mapping: list[int] = field(
        default_factory=list
    )  # Maps dropdown index to actual meld index

    # Winner tracking (for detecting new games and updating stats)
    last_winner: PlayerId | None = None

    # Bot automation timers
    bot_timeout_id: int | None = None
    bot_indicator_timeout_id: int | None = None
    bot_indicator_actor: PlayerId | None = None
    bot_indicator_name: str = ""
    bot_indicator_step: int = 0

    # Draw preview (shows newly drawn cards briefly)
    draw_preview_timeout_id: int | None = None
    draw_preview_base_hand: list[Card] | None = None
    draw_preview_inserted_cards: list[Card] | None = None
    draw_preview_restore_scroll: float | None = None

    def reset_bot_state(self) -> None:
        """Clear all bot-related state."""
        self.bot_timeout_id = None
        self.bot_indicator_timeout_id = None
        self.bot_indicator_actor = None
        self.bot_indicator_name = ""
        self.bot_indicator_step = 0

    def reset_draw_preview(self) -> None:
        """Clear all draw preview state."""
        self.draw_preview_timeout_id = None
        self.draw_preview_base_hand = None
        self.draw_preview_inserted_cards = None
        self.draw_preview_restore_scroll = None

    def reset_selection(self) -> None:
        """Clear hand selection."""
        self.selected_hand_indexes.clear()
        self.meld_index_mapping.clear()
