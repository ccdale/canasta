import pytest

from canasta.gui import main
from canasta.gui.actions import on_reminder
from canasta.gui.bootstrap import parse_args
from canasta.gui.utilities import resolve_target_meld_index
from canasta.model import Card, Meld, RuleError


class TestGUIEntryPoint:
    """Test that the GUI module is properly set up as an entry point."""

    def test_gui_main_is_importable(self):
        """Verify that the main entry point function exists and is callable."""
        assert callable(main)

    def test_gui_module_is_executable(self):
        """Verify the GUI module can be run as 'python -m canasta.gui'."""
        # This test just verifies the module structure is correct
        # The actual GUI startup requires GTK which may not be available in test env
        from canasta.gui import __main__  # noqa: F401

        assert True

    def test_extracted_gui_helpers_are_importable(self):
        """Verify deferred-import helper modules can be imported without GTK startup."""
        from canasta.gui import bot_runner, renderer  # noqa: F401

        assert True


class TestParseArgs:
    def test_defaults_to_random_north_and_human_south(self):
        args = parse_args([])

        assert args.north == "random"
        assert args.south == "human"

    def test_parse_args_respects_overrides(self):
        args = parse_args(["--north", "greedy", "--south", "safe", "--bot-seed", "42"])

        assert args.north == "greedy"
        assert args.south == "safe"
        assert args.bot_seed == 42

    def test_parse_args_for_all_desktop_file_variants(self):
        """Verify all bot variants used in .desktop files can be parsed.

        The .desktop files use these commands:
        - canasta.desktop: uv run canasta-gui (default: north=random, south=human)
        - canasta-random.desktop: uv run canasta-gui --north random
        - canasta-greedy.desktop: uv run canasta-gui --north greedy
        - canasta-safe.desktop: uv run canasta-gui --north safe
        - canasta-aggro.desktop: uv run canasta-gui --north aggro
        - canasta-planner.desktop: uv run canasta-gui --north planner
        - canasta-adaptive.desktop: uv run canasta-gui --north adaptive
        """
        variants = ["random", "greedy", "safe", "aggro", "planner", "adaptive"]
        for variant in variants:
            args = parse_args(["--north", variant])
            assert args.north == variant, f"Failed to parse --north {variant}"
            assert args.south == "human", (
                f"Default south should be human for --north {variant}"
            )


class _DummyUIState:
    def __init__(self, message: str = "") -> None:
        self.last_bot_move_message = message


class _DummyWindow:
    def __init__(self, message: str = "") -> None:
        self.ui_state = _DummyUIState(message)
        self.status = ""

    def _set_status(self, message: str) -> None:
        self.status = message


class TestReminderAction:
    def test_reminder_shows_previous_bot_move(self):
        window = _DummyWindow("[north:adaptive] drew 2 cards | discarded KH")

        on_reminder(window)

        assert window.status.startswith("Reminder: [north:adaptive]")

    def test_reminder_without_history_shows_helpful_message(self):
        window = _DummyWindow("")

        on_reminder(window)

        assert window.status == "No bot move to remind yet."


class TestResolveTargetMeldIndex:
    def test_returns_matching_meld_for_single_natural_rank(self):
        melds = [
            Meld(cards=[Card("A", "S"), Card("A", "H"), Card("A", "D")]),
            Meld(cards=[Card("K", "S"), Card("K", "H"), Card("K", "D")]),
        ]

        assert resolve_target_meld_index(melds, [Card("K", "C")]) == 1

    def test_returns_none_when_any_selected_card_is_wild(self):
        melds = [Meld(cards=[Card("A", "S"), Card("A", "H"), Card("A", "D")])]

        assert resolve_target_meld_index(melds, [Card("2", "C")]) is None
        assert resolve_target_meld_index(melds, [Card("A", "C"), Card("JOKER")]) is None

    def test_rejects_multiple_natural_ranks(self):
        melds = [Meld(cards=[Card("A", "S"), Card("A", "H"), Card("A", "D")])]

        with pytest.raises(RuleError, match="must all match one meld rank"):
            resolve_target_meld_index(melds, [Card("A", "C"), Card("K", "C")])

    def test_rejects_missing_target_meld(self):
        melds = [Meld(cards=[Card("A", "S"), Card("A", "H"), Card("A", "D")])]

        with pytest.raises(RuleError, match="no existing meld for rank K"):
            resolve_target_meld_index(melds, [Card("K", "C")])
