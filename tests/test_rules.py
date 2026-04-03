"""Tests for canasta.rules."""

import pytest

from canasta.model import Card, Meld
from canasta.rules import (
    can_add_cards_to_meld,
    can_discard,
    hand_score,
    meld_score,
    validate_meld_cards,
)


def c(rank: str, suit: str | None = None) -> Card:
    return Card(rank, suit)


class TestValidateMeldCards:
    def test_too_few_cards(self):
        ok, msg = validate_meld_cards([c("K", "S"), c("K", "H")])
        assert not ok
        assert "3" in msg

    def test_all_wilds_rejected(self):
        ok, msg = validate_meld_cards([c("2", "S"), c("2", "H"), c("JOKER")])
        assert not ok
        assert "wild" in msg

    def test_mismatched_naturals(self):
        ok, msg = validate_meld_cards([c("K", "S"), c("Q", "H"), c("K", "D")])
        assert not ok
        assert "same rank" in msg

    def test_more_wilds_than_naturals(self):
        ok, msg = validate_meld_cards([c("K", "S"), c("2", "H"), c("JOKER")])
        assert not ok
        assert "outnumber" in msg

    def test_valid_three_naturals(self):
        ok, msg = validate_meld_cards([c("K", "S"), c("K", "H"), c("K", "D")])
        assert ok

    def test_valid_with_wild(self):
        ok, msg = validate_meld_cards([c("K", "S"), c("K", "H"), c("2", "D")])
        assert ok

    def test_wilds_equal_naturals_allowed(self):
        ok, _ = validate_meld_cards([c("K", "S"), c("K", "H"), c("2", "D"), c("JOKER")])
        assert ok


class TestCanAddCardsToMeld:
    def test_valid_add(self):
        meld = Meld(cards=[c("Q", "S"), c("Q", "H"), c("Q", "D")])
        ok, _ = can_add_cards_to_meld(meld, [c("Q", "C")])
        assert ok

    def test_invalid_add_wrong_rank(self):
        meld = Meld(cards=[c("Q", "S"), c("Q", "H"), c("Q", "D")])
        ok, msg = can_add_cards_to_meld(meld, [c("K", "S")])
        assert not ok

    def test_too_many_wilds_after_add(self):
        # Q Q 2 + JOKER JOKER → 2 naturals, 3 wilds → rejected
        meld = Meld(cards=[c("Q", "S"), c("Q", "H"), c("2", "D")])
        ok, _ = can_add_cards_to_meld(meld, [c("JOKER"), c("JOKER")])
        assert not ok


class TestCanDiscard:
    def test_red_three_hearts(self):
        ok, msg = can_discard(c("3", "H"))
        assert not ok
        assert "red" in msg.lower()

    def test_red_three_diamonds(self):
        ok, _ = can_discard(c("3", "D"))
        assert not ok

    def test_black_three_ok(self):
        ok, _ = can_discard(c("3", "S"))
        assert ok

    def test_regular_card_ok(self):
        ok, _ = can_discard(c("A", "S"))
        assert ok

    def test_wild_two_ok(self):
        ok, _ = can_discard(c("2", "S"))
        assert ok


class TestHandScore:
    def test_joker_50(self):
        assert hand_score([c("JOKER")]) == 50

    def test_ace_20(self):
        assert hand_score([c("A", "S")]) == 20

    def test_two_20(self):
        assert hand_score([c("2", "H")]) == 20

    def test_king_10(self):
        assert hand_score([c("K", "S")]) == 10

    def test_seven_5(self):
        assert hand_score([c("7", "S")]) == 5

    def test_mixed_hand(self):
        cards = [c("JOKER"), c("A", "S"), c("K", "H"), c("7", "D")]
        assert hand_score(cards) == 50 + 20 + 10 + 5


class TestMeldScore:
    def test_empty(self):
        assert meld_score([]) == 0

    def test_no_canasta_bonus(self):
        melds = [Meld(cards=[c("K", "S"), c("K", "H"), c("K", "D")])]
        assert meld_score(melds) == 30

    def test_canasta_bonus(self):
        melds = [
            Meld(cards=[c("K", s) for s in ("S", "H", "D", "C")] + [c("K", "S")] * 3)
        ]
        assert meld_score(melds) == 7 * 10 + 300
