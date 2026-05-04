"""Tests for canasta.bots."""

from canasta.bot_strategies import (
    AdaptiveBot,
    AggroBot,
    GreedyBot,
    PlannerBot,
    RandomBot,
    SafeBot,
    _wild_augmented_candidates,
)
from canasta.bots import build_bot, play_bot_turn
from canasta.engine import CanastaEngine
from canasta.model import Card, Meld, PlayerId


def make_engine() -> CanastaEngine:
    return CanastaEngine(seed=42)


class TestBuildBot:
    def test_build_random(self):
        bot = build_bot("random", seed=1)
        assert bot.name == "random"

    def test_build_greedy(self):
        bot = build_bot("greedy")
        assert bot.name == "greedy"

    def test_build_safe(self):
        bot = build_bot("safe")
        assert bot.name == "safe"

    def test_build_aggro(self):
        bot = build_bot("aggro")
        assert bot.name == "aggro"

    def test_build_planner(self):
        bot = build_bot("planner")
        assert bot.name == "planner"

    def test_build_bot_strength_out_of_range_raises(self):
        import pytest

        with pytest.raises(ValueError, match="between 1 and 100"):
            build_bot("greedy", strength=0)

        with pytest.raises(ValueError, match="between 1 and 100"):
            build_bot("greedy", strength=101)


class TestBotTurns:
    def test_random_bot_completes_legal_turn(self):
        eng = make_engine()
        bot = RandomBot(rng=__import__("random").Random(1))
        current = eng.state.current_player

        actions = play_bot_turn(eng, bot)

        assert len(actions) >= 2
        assert eng.state.current_player != current
        assert not eng.state.turn_drawn

    def test_greedy_bot_melds_when_opening_available(self):
        eng = make_engine()
        hand = eng.state.players[PlayerId.NORTH].hand
        hand[0] = Card("A", "S")
        hand[1] = Card("A", "H")
        hand[2] = Card("A", "D")
        # Keep draw deterministic and harmless.
        eng.state.stock = [Card("4", "S"), Card("5", "S"), Card("6", "S")]

        actions = play_bot_turn(eng, GreedyBot())

        assert any(action.startswith("created") for action in actions)

    def test_bot_turn_discards_non_red_three(self):
        eng = make_engine()
        # Ensure a discardable card is present.
        eng.state.players[PlayerId.NORTH].hand[0] = Card("K", "S")

        actions = play_bot_turn(eng, GreedyBot())

        assert any(action.startswith("discarded ") for action in actions)

    def test_greedy_bot_can_choose_split_rank_opening(self):
        # Three kings + three eights can open as a split-rank meld in one action.
        hand = [
            Card("K", "S"),
            Card("K", "H"),
            Card("K", "D"),
            Card("8", "S"),
            Card("8", "H"),
            Card("8", "D"),
        ]

        idxs = GreedyBot().choose_meld_indexes(hand, opening_required=True)

        assert idxs is not None
        selected = [hand[i] for i in idxs]
        ranks = {card.rank for card in selected}
        assert ranks == {"K", "8"}

    def test_bot_picks_up_discard_before_drawing_unfrozen(self):
        eng = make_engine()
        eng.state.players[PlayerId.NORTH].melds.append(
            Meld(cards=[Card("7", "S"), Card("7", "H"), Card("7", "D")])
        )
        eng.state.discard = [Card("9", "C"), Card("A", "D")]
        hand = eng.state.players[PlayerId.NORTH].hand
        hand[0] = Card("A", "S")
        hand[1] = Card("A", "H")

        actions = play_bot_turn(eng, GreedyBot(strength=90))

        assert actions[0].startswith("picked up")

    def test_bot_picks_up_discard_before_drawing_frozen(self):
        eng = make_engine()
        eng.state.players[PlayerId.NORTH].melds.append(
            Meld(cards=[Card("7", "S"), Card("7", "H"), Card("7", "D")])
        )
        # Frozen because pile contains a freeze card (wild 2).
        eng.state.discard = [Card("2", "C"), Card("A", "D")]
        hand = eng.state.players[PlayerId.NORTH].hand
        hand[0] = Card("A", "S")
        hand[1] = Card("A", "H")

        actions = play_bot_turn(eng, PlannerBot(strength=90))

        assert actions[0].startswith("picked up")


class TestRandomBot:
    def test_random_bot_opening_candidates_include_split_rank(self):
        hand = [
            Card("K", "S"),
            Card("K", "H"),
            Card("K", "D"),
            Card("8", "S"),
            Card("8", "H"),
            Card("8", "D"),
        ]

        idxs = RandomBot(rng=__import__("random").Random(3)).choose_meld_indexes(
            hand, opening_required=True
        )

        assert idxs is not None
        selected = [hand[i] for i in idxs]
        ranks = {card.rank for card in selected}
        assert len(selected) >= 3
        assert ranks in ({"K"}, {"8"}, {"K", "8"})


class TestSafeBot:
    def test_safe_bot_skips_non_opening_meld(self):
        hand = [Card("A", "S"), Card("A", "H"), Card("A", "D")]
        assert SafeBot().choose_meld_indexes(hand, opening_required=False) is None

    def test_safe_bot_opening_prefers_lower_value_candidate(self):
        hand = [
            Card("A", "S"),
            Card("A", "H"),
            Card("A", "D"),  # 60 if used as opening meld
            Card("K", "S"),
            Card("K", "H"),
            Card("K", "D"),
            Card("K", "C"),
            Card("K", "S"),  # 50 with five kings
        ]
        idxs = SafeBot().choose_meld_indexes(hand, opening_required=True)
        assert idxs is not None
        ranks = [hand[i].rank for i in idxs]
        assert all(rank == "K" for rank in ranks)

    def test_safe_bot_discard_prefers_black_three(self):
        hand = [Card("K", "S"), Card("3", "S"), Card("A", "H")]
        idx = SafeBot().choose_discard_index(hand)
        assert hand[idx].label() == "3S"

    def test_safe_bot_discard_prefers_singleton_over_pair(self):
        hand = [Card("4", "S"), Card("4", "H"), Card("5", "C")]
        idx = SafeBot().choose_discard_index(hand)
        assert hand[idx].label() == "5C"

    def test_safe_bot_high_strength_melds_after_opening(self):
        hand = [Card("A", "S"), Card("A", "H"), Card("A", "D")]
        idxs = SafeBot(strength=80).choose_meld_indexes(hand, opening_required=False)
        assert idxs is not None

    def test_greedy_high_strength_preserves_grouped_rank(self):
        hand = [Card("8", "S"), Card("8", "H"), Card("9", "D")]

        low_idx = GreedyBot(strength=1).choose_discard_index(hand)
        high_idx = GreedyBot(strength=100).choose_discard_index(hand)

        assert hand[low_idx].label() == "8S"
        assert hand[high_idx].label() == "9D"


class TestAggroBot:
    def test_aggro_bot_prefers_longer_meld(self):
        hand = [
            Card("A", "S"),
            Card("A", "H"),
            Card("A", "D"),
            Card("A", "C"),
            Card("A", "S"),
        ]
        idxs = AggroBot().choose_meld_indexes(hand, opening_required=True)
        assert idxs is not None
        assert len(idxs) == 5

    def test_aggro_discard_prefers_high_points(self):
        hand = [Card("A", "S"), Card("7", "H"), Card("K", "D")]
        idx = AggroBot().choose_discard_index(hand)
        assert hand[idx].label() == "AS"

    def test_aggro_high_strength_avoids_wild_discard_when_possible(self):
        hand = [Card("2", "S"), Card("A", "H"), Card("7", "D")]

        low_idx = AggroBot(strength=1).choose_discard_index(hand)
        high_idx = AggroBot(strength=90).choose_discard_index(hand)

        assert hand[low_idx].label() == "2S"
        assert hand[high_idx].label() == "AH"


class TestPlannerBot:
    def test_planner_prefers_high_value_meld(self):
        hand = [
            Card("A", "S"),
            Card("A", "H"),
            Card("A", "D"),
            Card("K", "S"),
            Card("K", "H"),
            Card("K", "D"),
            Card("K", "C"),
            Card("K", "S"),
        ]
        idxs = PlannerBot().choose_meld_indexes(hand, opening_required=True)
        assert idxs is not None
        selected = [hand[i] for i in idxs]
        assert {card.rank for card in selected} == {"A", "K"}

    def test_planner_discard_keeps_wild_when_possible(self):
        hand = [Card("2", "S"), Card("7", "H"), Card("8", "D")]
        idx = PlannerBot().choose_discard_index(hand)
        assert hand[idx].rank != "2"


class TestDynamicOpeningThresholdIntegration:
    def test_bot_respects_engine_opening_minimum(self):
        eng = make_engine()
        eng.state.players[PlayerId.NORTH].score = 3000  # opening minimum now 120
        hand = eng.state.players[PlayerId.NORTH].hand
        hand[0] = Card("A", "S")
        hand[1] = Card("A", "H")
        hand[2] = Card("A", "D")
        hand[3] = Card("K", "S")
        # Keep draw deterministic and harmless.
        eng.state.stock = [Card("4", "S"), Card("5", "S"), Card("6", "S")]

        actions = play_bot_turn(eng, GreedyBot(strength=100))

        assert not any(action.startswith("created") for action in actions)


class TestWildAugmentedCandidates:
    def test_returns_empty_when_no_wilds(self):
        hand = [Card("K", "S"), Card("K", "H"), Card("K", "D")]
        assert _wild_augmented_candidates(hand) == []

    def test_returns_empty_when_no_natural_pairs(self):
        hand = [Card("K", "S"), Card("Q", "H"), Card("2", "D")]
        assert _wild_augmented_candidates(hand) == []

    def test_generates_pair_plus_wild(self):
        hand = [Card("K", "S"), Card("K", "H"), Card("2", "D")]
        candidates = _wild_augmented_candidates(hand)
        assert len(candidates) == 1
        selected = [hand[i] for i in candidates[0]]
        ranks = [c.rank for c in selected]
        assert ranks.count("K") == 2
        assert ranks.count("2") == 1

    def test_wilds_never_exceed_naturals(self):
        hand = [
            Card("K", "S"),
            Card("K", "H"),
            Card("2", "D"),
            Card("2", "S"),
            Card("JOKER", ""),
        ]
        candidates = _wild_augmented_candidates(hand)
        for idxs in candidates:
            cards = [hand[i] for i in idxs]
            naturals = sum(1 for c in cards if not c.is_wild())
            wilds = sum(1 for c in cards if c.is_wild())
            assert naturals >= wilds, f"wilds ({wilds}) exceeded naturals ({naturals})"

    def test_high_strength_greedy_uses_wild_in_meld(self):
        # Post-opening hand with 2 kings and 1 joker — high strength should meld them.
        hand = [Card("K", "S"), Card("K", "H"), Card("JOKER", ""), Card("4", "D")]
        idxs = GreedyBot(strength=80).choose_meld_indexes(hand, opening_required=False)
        assert idxs is not None
        selected = [hand[i] for i in idxs]
        ranks = [c.rank for c in selected]
        assert "K" in ranks
        assert "JOKER" in ranks

    def test_low_strength_greedy_ignores_wild_meld(self):
        # Below threshold: only natural 3+ groups qualify.
        hand = [Card("K", "S"), Card("K", "H"), Card("JOKER", ""), Card("4", "D")]
        idxs = GreedyBot(strength=30).choose_meld_indexes(hand, opening_required=False)
        # 2 kings is not a valid natural meld alone, so no candidate is available.
        assert idxs is None

    def test_safe_bot_very_low_strength_never_melds_post_opening(self):
        hand = [Card("A", "S"), Card("A", "H"), Card("A", "D"), Card("A", "C")]
        assert (
            SafeBot(strength=10).choose_meld_indexes(hand, opening_required=False)
            is None
        )

    def test_safe_bot_mid_strength_melds_large_groups(self):
        hand = [Card("A", "S"), Card("A", "H"), Card("A", "D"), Card("A", "C")]
        # strength 30 is in the 4+-group tier — 4 aces qualifies.
        idxs = SafeBot(strength=30).choose_meld_indexes(hand, opening_required=False)
        assert idxs is not None
        assert len(idxs) >= 4

    def test_safe_bot_mid_strength_skips_small_groups(self):
        hand = [Card("A", "S"), Card("A", "H"), Card("A", "D")]
        # Only 3 aces — below the 4-card threshold for the conservative tier.
        assert (
            SafeBot(strength=30).choose_meld_indexes(hand, opening_required=False)
            is None
        )

    def test_safe_bot_high_strength_melds_small_groups(self):
        hand = [Card("A", "S"), Card("A", "H"), Card("A", "D")]
        # strength 60 enters the standard natural-meld tier.
        idxs = SafeBot(strength=60).choose_meld_indexes(hand, opening_required=False)
        assert idxs is not None

    def test_safe_bot_very_high_strength_uses_wild_candidates(self):
        hand = [Card("K", "S"), Card("K", "H"), Card("2", "D"), Card("4", "C")]
        # strength 80 >= 70 gets wild augmented candidates.
        idxs = SafeBot(strength=80).choose_meld_indexes(hand, opening_required=False)
        assert idxs is not None
        selected = [hand[i] for i in idxs]
        assert any(c.is_wild() for c in selected)


class TestAdaptiveBot:
    def _rng(self) -> __import__("random").Random:
        return __import__("random").Random(42)

    def test_build_adaptive(self):
        from canasta.bots import build_bot
        bot = build_bot("adaptive", seed=1, strength=50)
        assert bot.name == "adaptive"

    def test_low_strength_meld_is_random(self):
        # At strength 10 choose_meld_indexes returns a random candidate or None.
        hand = [Card("A", "S"), Card("A", "H"), Card("A", "D"), Card("K", "S")]
        bot = AdaptiveBot(rng=self._rng(), strength=10)
        # Should not raise; result is None or a valid index list.
        result = bot.choose_meld_indexes(hand, opening_required=True)
        if result is not None:
            assert all(0 <= i < len(hand) for i in result)

    def test_low_strength_discard_is_random(self):
        hand = [Card("A", "S"), Card("K", "H"), Card("7", "D")]
        bot = AdaptiveBot(rng=self._rng(), strength=10)
        idx = bot.choose_discard_index(hand)
        assert 0 <= idx < len(hand)

    def test_safe_tier_never_melds_small_post_opening_group(self):
        hand = [Card("A", "S"), Card("A", "H"), Card("A", "D")]
        bot = AdaptiveBot(rng=self._rng(), strength=35)
        # 3 aces < 4 — safe tier skips post-opening melds below 4-card threshold.
        assert bot.choose_meld_indexes(hand, opening_required=False) is None

    def test_safe_tier_discards_defensively(self):
        # Prefers black three over high-point card.
        hand = [Card("K", "S"), Card("3", "S"), Card("A", "H")]
        bot = AdaptiveBot(rng=self._rng(), strength=40)
        idx = bot.choose_discard_index(hand)
        assert hand[idx].label() == "3S"

    def test_planner_tier_melds_with_wild(self):
        hand = [Card("K", "S"), Card("K", "H"), Card("JOKER", ""), Card("4", "D")]
        bot = AdaptiveBot(rng=self._rng(), strength=65)
        idxs = bot.choose_meld_indexes(hand, opening_required=False)
        assert idxs is not None
        selected = [hand[i] for i in idxs]
        assert any(c.is_wild() for c in selected)

    def test_planner_tier_preserves_wilds_on_discard(self):
        hand = [Card("2", "S"), Card("7", "H"), Card("8", "D")]
        bot = AdaptiveBot(rng=self._rng(), strength=65)
        idx = bot.choose_discard_index(hand)
        assert hand[idx].rank != "2"

    def test_aggro_tier_melds_most_cards(self):
        hand = [
            Card("A", "S"), Card("A", "H"), Card("A", "D"), Card("A", "C"),
            Card("K", "S"), Card("K", "H"), Card("K", "D"),
        ]
        bot = AdaptiveBot(rng=self._rng(), strength=90)
        idxs = bot.choose_meld_indexes(hand, opening_required=True)
        assert idxs is not None
        assert len(idxs) >= 6

    def test_aggro_tier_sheds_high_point_natural_not_wild(self):
        hand = [Card("2", "S"), Card("A", "H"), Card("7", "D")]
        bot = AdaptiveBot(rng=self._rng(), strength=90)
        idx = bot.choose_discard_index(hand)
        assert hand[idx].label() == "AH"
