"""Tests for canasta.model."""

import pytest

from canasta.model import (
    RANKS,
    SUITS,
    WILD_RANKS,
    Card,
    Meld,
    PlayerId,
    build_double_deck,
)


class TestCard:
    def test_label_regular(self):
        assert Card("K", "S").label() == "KS"

    def test_label_joker(self):
        assert Card("JOKER").label() == "JOKER"

    def test_is_wild_joker(self):
        assert Card("JOKER").is_wild()

    def test_is_wild_two(self):
        assert Card("2", "H").is_wild()

    def test_is_not_wild(self):
        assert not Card("A", "S").is_wild()

    def test_card_frozen(self):
        card = Card("A", "S")
        with pytest.raises(Exception):
            card.rank = "K"  # type: ignore[misc]


class TestMeld:
    def _meld(self, *specs: tuple[str, str | None]) -> Meld:
        return Meld(cards=[Card(r, s) for r, s in specs])

    def test_natural_rank(self):
        m = self._meld(("K", "S"), ("K", "H"), ("2", "D"))
        assert m.natural_rank == "K"

    def test_natural_count(self):
        m = self._meld(("K", "S"), ("K", "H"), ("2", "D"))
        assert m.natural_count == 2

    def test_wild_count(self):
        m = self._meld(("K", "S"), ("K", "H"), ("2", "D"))
        assert m.wild_count == 1

    def test_is_canasta_false(self):
        m = Meld(cards=[Card("K", "S")] * 6)
        assert not m.is_canasta

    def test_is_canasta_true(self):
        m = Meld(cards=[Card("K", "S")] * 7)
        assert m.is_canasta


class TestBuildDoubleDeck:
    def setup_method(self):
        self.deck = build_double_deck()

    def test_total_cards(self):
        # 13 ranks × 4 suits × 2 = 104, plus 4 jokers = 108
        assert len(self.deck) == 108

    def test_four_jokers(self):
        jokers = [c for c in self.deck if c.rank == "JOKER"]
        assert len(jokers) == 4

    def test_each_regular_card_twice(self):
        for rank in RANKS:
            for suit in SUITS:
                count = sum(1 for c in self.deck if c.rank == rank and c.suit == suit)
                assert count == 2, f"expected 2 of {rank}{suit}, got {count}"
