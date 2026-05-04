"""Tests for canasta.rules."""

from canasta.model import Card, Meld
from canasta.rules import (
    MATCH_TARGET_SCORE,
    OPENING_MELD_MINIMUM,
    can_add_cards_to_meld,
    can_discard,
    can_pickup_frozen_discard,
    discard_pile_is_frozen,
    hand_penalty,
    hand_score,
    is_discard_freeze_card,
    meld_score,
    opening_meld_minimum_for_score,
    opening_meld_value,
    split_meld_cards,
    validate_meld_cards,
    validate_pickup_cards,
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


class TestSplitMeldCards:
    def test_single_rank_returns_one_group(self):
        groups, msg = split_meld_cards([c("K", "S"), c("K", "H"), c("K", "D")])

        assert msg == "ok"
        assert groups == [[c("K", "S"), c("K", "H"), c("K", "D")]]

    def test_opening_split_across_natural_ranks(self):
        groups, msg = split_meld_cards(
            [
                c("6", "S"),
                c("6", "H"),
                c("6", "D"),
                c("6", "C"),
                c("Q", "S"),
                c("Q", "H"),
                c("Q", "D"),
            ],
            allow_multi_rank=True,
        )

        assert msg == "ok"
        assert groups is not None
        assert len(groups) == 2
        assert {group[0].rank for group in groups} == {"6", "Q"}

    def test_opening_split_allows_wild_cards(self):
        groups, msg = split_meld_cards(
            [
                c("A", "S"),
                c("A", "H"),
                c("A", "D"),
                c("K", "S"),
                c("K", "H"),
                c("2", "C"),
            ],
            allow_multi_rank=True,
        )

        assert msg == "ok"
        assert groups is not None
        assert len(groups) == 2
        by_rank = {
            next(card.rank for card in group if not card.is_wild()): group
            for group in groups
        }
        assert len(by_rank["A"]) == 3
        assert len(by_rank["K"]) == 3
        assert sum(1 for card in by_rank["K"] if card.is_wild()) == 1

    def test_opening_split_rejects_unassignable_wild_cards(self):
        groups, msg = split_meld_cards(
            [
                c("A", "S"),
                c("A", "H"),
                c("K", "S"),
                c("K", "H"),
                c("2", "C"),
                c("2", "D"),
                c("2", "H"),
                c("JOKER"),
                c("JOKER"),
            ],
            allow_multi_rank=True,
        )

        assert groups is None
        assert "cannot assign" in msg


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


class TestDiscardPileFreeze:
    def test_wild_card_is_freeze_card(self):
        assert is_discard_freeze_card(c("2", "S"))
        assert is_discard_freeze_card(c("JOKER"))

    def test_black_three_is_freeze_card(self):
        assert is_discard_freeze_card(c("3", "S"))
        assert is_discard_freeze_card(c("3", "C"))

    def test_regular_card_not_freeze_card(self):
        assert not is_discard_freeze_card(c("A", "S"))

    def test_discard_pile_is_frozen_when_contains_freeze_card(self):
        discard = [c("9", "S"), c("3", "C"), c("A", "D")]
        assert discard_pile_is_frozen(discard)

    def test_discard_pile_not_frozen_without_freeze_card(self):
        discard = [c("9", "S"), c("8", "C"), c("A", "D")]
        assert not discard_pile_is_frozen(discard)


class TestCanPickupFrozenDiscard:
    def test_matching_natural_pair_allowed(self):
        ok, _ = can_pickup_frozen_discard(c("A", "D"), [c("A", "S"), c("A", "H")])
        assert ok

    def test_wrong_pair_rejected(self):
        ok, msg = can_pickup_frozen_discard(c("A", "D"), [c("K", "S"), c("K", "H")])
        assert not ok
        assert "matching" in msg

    def test_wild_in_pair_rejected(self):
        ok, msg = can_pickup_frozen_discard(c("A", "D"), [c("A", "S"), c("JOKER")])
        assert not ok
        assert "natural" in msg

    def test_wrong_card_count_rejected(self):
        ok, msg = can_pickup_frozen_discard(c("A", "D"), [c("A", "S")])
        assert not ok
        assert "exactly 2" in msg

    def test_freeze_card_on_top_rejected(self):
        ok, msg = can_pickup_frozen_discard(c("3", "S"), [c("3", "S"), c("3", "C")])
        assert not ok
        assert "black three" in msg


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


class TestHandPenalty:
    def test_empty_hand(self):
        assert hand_penalty([]) == 0

    def test_same_values_as_hand_score(self):
        cards = [c("JOKER"), c("A", "S"), c("K", "H"), c("7", "D")]
        assert hand_penalty(cards) == hand_score(cards)

    def test_regular_cards(self):
        assert hand_penalty([c("K", "S"), c("7", "H")]) == 15


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


class TestOpeningMeldValue:
    def test_all_naturals(self):
        # 3 × K = 30
        cards = [c("K", "S"), c("K", "H"), c("K", "D")]
        assert opening_meld_value(cards) == 30

    def test_wilds_excluded(self):
        # A + A + JOKER: wild excluded → 2 × 20 = 40
        cards = [c("A", "S"), c("A", "H"), c("JOKER")]
        assert opening_meld_value(cards) == 40

    def test_minimum_constant(self):
        assert OPENING_MELD_MINIMUM == 50

    def test_meets_minimum(self):
        # 2 × A + K = 50
        cards = [c("A", "S"), c("A", "H"), c("K", "D")]
        assert opening_meld_value(cards) >= OPENING_MELD_MINIMUM


class TestOpeningMeldMinimumForScore:
    def test_negative_score_requires_15(self):
        assert opening_meld_minimum_for_score(-1) == 15

    def test_sub_1500_score_requires_50(self):
        assert opening_meld_minimum_for_score(1499) == 50

    def test_sub_3000_score_requires_90(self):
        assert opening_meld_minimum_for_score(1500) == 90

    def test_3000_and_above_requires_120(self):
        assert opening_meld_minimum_for_score(3000) == 120

    def test_match_target_constant(self):
        assert MATCH_TARGET_SCORE == 5000


class TestValidatePickupCards:
    def test_single_rank_returns_one_group(self):
        top = c("A", "D")
        groups, msg = validate_pickup_cards(top, [c("A", "S"), c("A", "H")])

        assert msg == "ok"
        assert len(groups) == 1
        assert {card.rank for card in groups[0]} == {"A"}

    def test_split_rank_opening_returns_two_groups(self):
        # 3 tens + top discard queen, with 2 more queens in hand
        top = c("Q", "D")
        hand = [c("T", "S"), c("T", "H"), c("T", "D"), c("Q", "S"), c("Q", "H")]
        groups, msg = validate_pickup_cards(top, hand, allow_multi_rank=True)

        assert msg == "ok"
        assert len(groups) == 2
        # First group must contain the top discard (queen group)
        assert groups[0][0].rank == "Q"
        assert {card.rank for card in groups[1]} == {"T"}

    def test_split_rank_requires_allow_multi_rank(self):
        top = c("Q", "D")
        hand = [c("T", "S"), c("T", "H"), c("T", "D"), c("Q", "S"), c("Q", "H")]
        groups, msg = validate_pickup_cards(top, hand, allow_multi_rank=False)

        assert groups is None

    def test_split_rank_allows_wild_in_non_discard_group(self):
        # Q♠ Q♥ + top Q♦ = 3 queens; T♠ T♥ + wild 2♣ = 3-card ten meld → all valid.
        top = c("Q", "D")
        hand = [c("Q", "S"), c("Q", "H"), c("T", "S"), c("T", "H"), c("2", "C")]
        groups, msg = validate_pickup_cards(top, hand, allow_multi_rank=True)

        assert groups is not None
        assert len(groups) == 2
        assert all(
            c("Q", "D").rank == card.rank for card in groups[0] if not card.is_wild()
        )

    def test_split_rank_rejects_too_many_wilds(self):
        # 2 queens + top queen + 1 ten, but 3 wilds — wilds exceed naturals in T group.
        top = c("Q", "D")
        hand = [
            c("Q", "S"),
            c("Q", "H"),
            c("T", "S"),
            c("2", "C"),
            c("2", "H"),
            c("2", "D"),
        ]
        groups, msg = validate_pickup_cards(top, hand, allow_multi_rank=True)

        # T group: 1 natural, wilds would exceed it → validation fails
        assert groups is None

    def test_split_rank_rejects_group_with_fewer_than_3(self):
        # Only 2 tens available — tops up to 2+1=2 in group after discard added
        top = c("Q", "D")
        hand = [c("T", "S"), c("T", "H"), c("Q", "S"), c("Q", "H")]
        groups, msg = validate_pickup_cards(top, hand, allow_multi_rank=True)

        assert groups is None
        assert "at least 3" in msg
