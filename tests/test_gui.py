import pytest

from canasta.gui import _parse_args, _resolve_target_meld_index
from canasta.model import Card, Meld, RuleError


class TestParseArgs:
    def test_defaults_to_random_north_and_human_south(self):
        args = _parse_args([])

        assert args.north == "random"
        assert args.south == "human"


class TestResolveTargetMeldIndex:
    def test_returns_matching_meld_for_single_natural_rank(self):
        melds = [
            Meld(cards=[Card("A", "S"), Card("A", "H"), Card("A", "D")]),
            Meld(cards=[Card("K", "S"), Card("K", "H"), Card("K", "D")]),
        ]

        assert _resolve_target_meld_index(melds, [Card("K", "C")]) == 1

    def test_returns_none_when_any_selected_card_is_wild(self):
        melds = [Meld(cards=[Card("A", "S"), Card("A", "H"), Card("A", "D")])]

        assert _resolve_target_meld_index(melds, [Card("2", "C")]) is None
        assert (
            _resolve_target_meld_index(melds, [Card("A", "C"), Card("JOKER")]) is None
        )

    def test_rejects_multiple_natural_ranks(self):
        melds = [Meld(cards=[Card("A", "S"), Card("A", "H"), Card("A", "D")])]

        with pytest.raises(RuleError, match="must all match one meld rank"):
            _resolve_target_meld_index(melds, [Card("A", "C"), Card("K", "C")])

    def test_rejects_missing_target_meld(self):
        melds = [Meld(cards=[Card("A", "S"), Card("A", "H"), Card("A", "D")])]

        with pytest.raises(RuleError, match="no existing meld for rank K"):
            _resolve_target_meld_index(melds, [Card("K", "C")])
