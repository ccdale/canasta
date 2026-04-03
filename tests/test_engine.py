"""Tests for canasta.engine — deterministic via seed."""

import pytest

from canasta.engine import CanastaEngine, RuleError
from canasta.model import Card, Meld, PlayerId

SEED = 42  # fixed for determinism


def make_engine() -> CanastaEngine:
    return CanastaEngine(seed=SEED)


class TestInit:
    def test_each_player_gets_11_cards(self):
        eng = make_engine()
        assert len(eng.state.players[PlayerId.NORTH].hand) == 11
        assert len(eng.state.players[PlayerId.SOUTH].hand) == 11

    def test_stock_has_85_cards(self):
        # 108 - 22 dealt - 1 discard = 85
        eng = make_engine()
        assert len(eng.state.stock) == 85

    def test_one_card_in_discard(self):
        eng = make_engine()
        assert len(eng.state.discard) == 1

    def test_north_starts(self):
        eng = make_engine()
        assert eng.state.current_player == PlayerId.NORTH

    def test_turn_not_drawn(self):
        eng = make_engine()
        assert not eng.state.turn_drawn


class TestDrawStock:
    def test_draw_adds_two_to_hand(self):
        eng = make_engine()
        before = len(eng.current_hand())
        eng.draw_stock()
        assert len(eng.current_hand()) == before + 2

    def test_draw_removes_from_stock(self):
        eng = make_engine()
        before = len(eng.state.stock)
        eng.draw_stock()
        assert len(eng.state.stock) == before - 2

    def test_sets_turn_drawn(self):
        eng = make_engine()
        eng.draw_stock()
        assert eng.state.turn_drawn

    def test_double_draw_raises(self):
        eng = make_engine()
        eng.draw_stock()
        with pytest.raises(RuleError, match="already drew"):
            eng.draw_stock()


class TestCreateMeld:
    def _draw_and_inject(self, eng: CanastaEngine, cards: list[Card]) -> list[int]:
        """Replace last N cards in current hand with the given cards and return their indexes."""
        eng.draw_stock()
        hand = eng.current_hand()
        start = len(hand) - len(cards)
        for i, card in enumerate(cards):
            hand[start + i] = card
        return list(range(start, start + len(cards)))

    def test_create_valid_meld(self):
        eng = make_engine()
        idxs = self._draw_and_inject(
            eng, [Card("K", "S"), Card("K", "H"), Card("K", "D")]
        )
        result = eng.create_meld(idxs)
        assert "meld" in result.message
        assert len(eng.state.players[PlayerId.NORTH].melds) == 1

    def test_meld_without_draw_raises(self):
        eng = make_engine()
        with pytest.raises(RuleError, match="draw"):
            eng.create_meld([0, 1, 2])

    def test_invalid_meld_raises(self):
        eng = make_engine()
        idxs = self._draw_and_inject(
            eng, [Card("K", "S"), Card("Q", "H"), Card("J", "D")]
        )
        with pytest.raises(RuleError):
            eng.create_meld(idxs)

    def test_cards_returned_to_hand_on_failure(self):
        eng = make_engine()
        idxs = self._draw_and_inject(
            eng, [Card("K", "S"), Card("Q", "H"), Card("J", "D")]
        )
        hand_before = len(eng.current_hand())
        with pytest.raises(RuleError):
            eng.create_meld(idxs)
        assert len(eng.current_hand()) == hand_before


class TestAddToMeld:
    def _setup_with_meld(self) -> tuple[CanastaEngine, int]:
        eng = make_engine()
        eng.draw_stock()
        hand = eng.current_hand()
        # Inject 4 Kings for the meld + one extra
        for i in range(4):
            hand[i] = Card("K", ("S", "H", "D", "C")[i])
        eng.create_meld([0, 1, 2])
        return eng, 0  # meld_index=0

    def test_add_valid_card(self):
        eng, meld_idx = self._setup_with_meld()
        # Find the injected 4th king's position after meld creation (it's at index 0)
        hand = eng.current_hand()
        king_idx = next(i for i, c in enumerate(hand) if c.rank == "K")
        before_len = len(eng.state.players[PlayerId.NORTH].melds[meld_idx].cards)
        eng.add_to_meld(meld_idx, [king_idx])
        after_len = len(eng.state.players[PlayerId.NORTH].melds[meld_idx].cards)
        assert after_len == before_len + 1

    def test_add_without_draw_raises(self):
        eng = make_engine()
        with pytest.raises(RuleError, match="draw"):
            eng.add_to_meld(0, [0])

    def test_invalid_meld_index_raises(self):
        eng = make_engine()
        eng.draw_stock()
        with pytest.raises(RuleError, match="invalid meld"):
            eng.add_to_meld(99, [0])


class TestDiscard:
    def _draw_and_get_safe_discard(self, eng: CanastaEngine) -> int:
        eng.draw_stock()
        hand = eng.current_hand()
        # Inject a safe card (non-red-3) in position 0
        hand[0] = Card("K", "S")
        return 0

    def test_discard_removes_from_hand(self):
        eng = make_engine()
        idx = self._draw_and_get_safe_discard(eng)
        before = len(eng.current_hand())
        eng.discard(idx)
        assert len(eng.state.players[PlayerId.NORTH].hand) == before - 1

    def test_discard_adds_to_pile(self):
        eng = make_engine()
        idx = self._draw_and_get_safe_discard(eng)
        before_pile = len(eng.state.discard)
        eng.discard(idx)
        assert len(eng.state.discard) == before_pile + 1

    def test_discard_ends_turn(self):
        eng = make_engine()
        idx = self._draw_and_get_safe_discard(eng)
        eng.discard(idx)
        assert eng.state.current_player == PlayerId.SOUTH
        assert not eng.state.turn_drawn

    def test_discard_without_draw_raises(self):
        eng = make_engine()
        with pytest.raises(RuleError, match="draw"):
            eng.discard(0)

    def test_discard_red_three_raises(self):
        eng = make_engine()
        eng.draw_stock()
        hand = eng.current_hand()
        hand[0] = Card("3", "H")
        with pytest.raises(RuleError, match="red"):
            eng.discard(0)

    def test_discard_invalid_index_raises(self):
        eng = make_engine()
        eng.draw_stock()
        with pytest.raises(RuleError, match="invalid"):
            eng.discard(999)


class TestScore:
    def test_score_starts_zero(self):
        eng = make_engine()
        assert eng.score(PlayerId.NORTH) == 0
        assert eng.score(PlayerId.SOUTH) == 0
