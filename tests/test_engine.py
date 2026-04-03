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

    def test_stock_conservation_after_init(self):
        # stock + red threes placed = 85 (108 - 22 dealt - 1 discard)
        eng = make_engine()
        red_three_count = sum(len(p.red_threes) for p in eng.state.players.values())
        assert len(eng.state.stock) + red_three_count == 85

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
            eng, [Card("A", "S"), Card("A", "H"), Card("A", "D")]
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
        # Inject 4 Aces — opening value 4×20 = 80 ≥ 50, plus one extra
        for i in range(4):
            hand[i] = Card("A", ("S", "H", "D", "C")[i])
        eng.create_meld([0, 1, 2])
        return eng, 0  # meld_index=0

    def test_add_valid_card(self):
        eng, meld_idx = self._setup_with_meld()
        # The 4th Ace (index 3) stays in hand after create_meld([0,1,2])
        hand = eng.current_hand()
        ace_idx = next(i for i, c in enumerate(hand) if c.rank == "A")
        before_len = len(eng.state.players[PlayerId.NORTH].melds[meld_idx].cards)
        eng.add_to_meld(meld_idx, [ace_idx])
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


class TestPickupDiscard:
    def _set_discard(self, eng: CanastaEngine, cards: list[Card]) -> None:
        eng.state.discard = list(cards)

    def _inject_hand(
        self, eng: CanastaEngine, cards: list[Card], start: int = 0
    ) -> None:
        hand = eng.current_hand()
        for i, card in enumerate(cards):
            hand[start + i] = card

    def test_pickup_creates_meld_with_top_discard(self):
        eng = make_engine()
        self._set_discard(eng, [Card("9", "C"), Card("A", "D")])
        self._inject_hand(eng, [Card("A", "S"), Card("A", "H")])

        result = eng.pickup_discard([0, 1])

        meld = eng.state.players[PlayerId.NORTH].melds[0]
        assert "picked up" in result.message
        assert [card.label() for card in meld.cards] == ["AS", "AH", "AD"]

    def test_pickup_moves_rest_of_pile_to_hand(self):
        eng = make_engine()
        self._set_discard(eng, [Card("9", "C"), Card("8", "S"), Card("A", "D")])
        self._inject_hand(eng, [Card("A", "S"), Card("A", "H")])

        eng.pickup_discard([0, 1])

        hand_labels = {card.label() for card in eng.current_hand()}
        assert "9C" in hand_labels
        assert "8S" in hand_labels
        assert eng.state.discard == []

    def test_pickup_sets_turn_drawn(self):
        eng = make_engine()
        self._set_discard(eng, [Card("A", "D")])
        self._inject_hand(eng, [Card("A", "S"), Card("A", "H")])

        eng.pickup_discard([0, 1])

        assert eng.state.turn_drawn

    def test_pickup_after_draw_raises(self):
        eng = make_engine()
        eng.draw_stock()
        with pytest.raises(RuleError, match="already drew"):
            eng.pickup_discard([0, 1])

    def test_pickup_invalid_meld_rolls_back(self):
        eng = make_engine()
        self._set_discard(eng, [Card("A", "D")])
        self._inject_hand(eng, [Card("K", "S"), Card("Q", "H")])
        hand_before = len(eng.current_hand())
        discard_before = [card.label() for card in eng.state.discard]

        with pytest.raises(RuleError, match="cannot pick up discard pile"):
            eng.pickup_discard([0, 1])

        assert len(eng.current_hand()) == hand_before
        assert [card.label() for card in eng.state.discard] == discard_before

    def test_pickup_opening_threshold_applies(self):
        eng = make_engine()
        self._set_discard(eng, [Card("K", "D")])
        self._inject_hand(eng, [Card("K", "S"), Card("K", "H")])

        with pytest.raises(RuleError, match="opening meld"):
            eng.pickup_discard([0, 1])

    def test_pickup_after_opening_meld_ignores_threshold(self):
        eng = make_engine()
        eng.state.players[PlayerId.NORTH].melds.append(
            Meld(cards=[Card("A", "S"), Card("A", "H"), Card("A", "D")])
        )
        self._set_discard(eng, [Card("7", "D")])
        self._inject_hand(eng, [Card("7", "S"), Card("7", "H")])

        result = eng.pickup_discard([0, 1])

        assert "picked up" in result.message

    def test_pickup_empty_discard_raises(self):
        eng = make_engine()
        eng.state.discard = []
        with pytest.raises(RuleError, match="empty"):
            eng.pickup_discard([0, 1])

    def test_frozen_pile_allows_matching_natural_pair(self):
        eng = make_engine()
        self._set_discard(eng, [Card("3", "C"), Card("A", "D")])
        self._inject_hand(eng, [Card("A", "S"), Card("A", "H")])

        result = eng.pickup_discard([0, 1])

        assert "picked up" in result.message

    def test_frozen_pile_rejects_non_matching_pair(self):
        eng = make_engine()
        self._set_discard(eng, [Card("3", "C"), Card("A", "D")])
        self._inject_hand(eng, [Card("K", "S"), Card("K", "H")])

        with pytest.raises(RuleError, match="matching the top discard"):
            eng.pickup_discard([0, 1])

    def test_frozen_pile_rejects_extra_cards(self):
        eng = make_engine()
        self._set_discard(eng, [Card("3", "C"), Card("A", "D")])
        self._inject_hand(eng, [Card("A", "S"), Card("A", "H"), Card("A", "C")])

        with pytest.raises(RuleError, match="exactly 2"):
            eng.pickup_discard([0, 1, 2])

    def test_frozen_pile_rejects_black_three_on_top(self):
        eng = make_engine()
        self._set_discard(eng, [Card("A", "D"), Card("3", "S")])
        self._inject_hand(eng, [Card("3", "C"), Card("3", "S")])

        with pytest.raises(RuleError, match="black three"):
            eng.pickup_discard([0, 1])


class TestScore:
    def test_no_meld_score_at_start(self):
        # No melds have been played yet; only red-three bonus may be present.
        from canasta.rules import meld_score

        eng = make_engine()
        for player in eng.state.players.values():
            assert meld_score(player.melds) == 0


class TestRedThrees:
    """Red three auto-meld behaviour."""

    def _engine_with_red_three_in_hand(self) -> CanastaEngine:
        """Return a fresh engine with a red three injected into NORTH's hand slot 0."""
        eng = CanastaEngine(seed=SEED)
        # Clear any red threes already auto-melded so the hand has room.
        # Inject a fresh red three at position 0 (overwriting whatever is there).
        eng.state.players[PlayerId.NORTH].hand[0] = Card("3", "H")
        return eng

    def test_red_threes_removed_from_hand_at_init(self):
        eng = make_engine()
        for player in eng.state.players.values():
            assert all(not c.is_red_three() for c in player.hand)

    def test_red_threes_placed_in_red_threes_list_at_init(self):
        # seed=42 deals 3H and 3D to NORTH
        eng = make_engine()
        north = eng.state.players[PlayerId.NORTH]
        assert len(north.red_threes) == 2
        assert all(c.is_red_three() for c in north.red_threes)

    def test_hand_size_preserved_after_red_three_replacement(self):
        # Each red three drawn at init is replaced; hand stays at 11.
        eng = make_engine()
        for player in eng.state.players.values():
            assert len(player.hand) == 11

    def test_red_three_drawn_during_turn_auto_melded(self):
        eng = make_engine()
        # Inject a red three into the stock so it will be drawn.
        eng.state.stock.append(Card("3", "D"))
        before_red_threes = len(eng.state.players[PlayerId.NORTH].red_threes)
        result = eng.draw_stock()
        after_red_threes = len(eng.state.players[PlayerId.NORTH].red_threes)
        assert after_red_threes > before_red_threes
        assert "auto-melded" in result.message

    def test_hand_size_stable_after_mid_turn_red_three(self):
        eng = make_engine()
        eng.state.stock.append(Card("3", "H"))
        before = len(eng.current_hand())
        eng.draw_stock()
        # Drew 2, one was a red three (replaced from stock) → net +2 in hand
        assert len(eng.current_hand()) == before + 2

    def test_red_three_score_one(self):
        from canasta.rules import red_three_score

        assert red_three_score([Card("3", "H")]) == 100

    def test_red_three_score_two(self):
        from canasta.rules import red_three_score

        assert red_three_score([Card("3", "H"), Card("3", "D")]) == 200

    def test_red_three_score_all_four(self):
        from canasta.rules import red_three_score

        cards = [Card("3", "H"), Card("3", "D"), Card("3", "H"), Card("3", "D")]
        assert red_three_score(cards) == 800

    def test_score_includes_red_threes(self):
        eng = make_engine()
        north = eng.state.players[PlayerId.NORTH]
        from canasta.rules import red_three_score

        expected = red_three_score(north.red_threes)
        assert eng.score(PlayerId.NORTH) == expected


class TestOpeningMeld:
    """First meld must meet the OPENING_MELD_MINIMUM natural-card point threshold."""

    def _draw_and_inject(self, eng: CanastaEngine, cards: list[Card]) -> list[int]:
        eng.draw_stock()
        hand = eng.current_hand()
        start = len(hand) - len(cards)
        for i, card in enumerate(cards):
            hand[start + i] = card
        return list(range(start, start + len(cards)))

    def test_opening_meld_below_minimum_rejected(self):
        # 3 × 7 = 15 points — below 50
        eng = make_engine()
        idxs = self._draw_and_inject(
            eng, [Card("7", "S"), Card("7", "H"), Card("7", "D")]
        )
        with pytest.raises(RuleError, match="opening meld"):
            eng.create_meld(idxs)

    def test_opening_meld_cards_returned_on_rejection(self):
        eng = make_engine()
        idxs = self._draw_and_inject(
            eng, [Card("7", "S"), Card("7", "H"), Card("7", "D")]
        )
        before = len(eng.current_hand())
        with pytest.raises(RuleError):
            eng.create_meld(idxs)
        assert len(eng.current_hand()) == before

    def test_opening_meld_at_minimum_accepted(self):
        # 5 × K = 50 points — exactly at the minimum
        eng = make_engine()
        idxs = self._draw_and_inject(
            eng,
            [
                Card("K", "S"),
                Card("K", "H"),
                Card("K", "D"),
                Card("K", "C"),
                Card("K", "S"),
            ],
        )
        result = eng.create_meld(idxs)
        assert "meld" in result.message

    def test_opening_meld_above_minimum_accepted(self):
        # 3 × K = 30 pts < 50 — would fail, so use 3 × A = 60 pts
        eng = make_engine()
        idxs = self._draw_and_inject(
            eng, [Card("A", "S"), Card("A", "H"), Card("A", "D")]
        )
        result = eng.create_meld(idxs)
        assert "meld" in result.message

    def test_wilds_excluded_from_opening_value(self):
        # A + A + JOKER: naturals = 2 × 20 = 40 pts → still below 50
        eng = make_engine()
        idxs = self._draw_and_inject(
            eng, [Card("A", "S"), Card("A", "H"), Card("JOKER")]
        )
        with pytest.raises(RuleError, match="opening meld"):
            eng.create_meld(idxs)

    def test_subsequent_meld_not_subject_to_minimum(self):
        # After one valid opening, a second meld of low value is fine.
        eng = make_engine()
        # First: open with 3 × A (60 pts) — draws in the same turn
        idxs1 = self._draw_and_inject(
            eng, [Card("A", "S"), Card("A", "H"), Card("A", "D")]
        )
        eng.create_meld(idxs1)
        # Still the same turn — inject low-value cards directly and meld
        hand = eng.current_hand()
        hand[0] = Card("7", "S")
        hand[1] = Card("7", "H")
        hand[2] = Card("7", "D")
        result = eng.create_meld([0, 1, 2])
        assert "meld" in result.message
