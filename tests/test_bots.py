"""Tests for canasta.bots."""

from canasta.bots import (
    AggroBot,
    GreedyBot,
    PlannerBot,
    RandomBot,
    SafeBot,
    build_bot,
    play_bot_turn,
)
from canasta.engine import CanastaEngine
from canasta.model import Card, PlayerId


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

        assert any("created meld" in action for action in actions)

    def test_bot_turn_discards_non_red_three(self):
        eng = make_engine()
        # Ensure a discardable card is present.
        eng.state.players[PlayerId.NORTH].hand[0] = Card("K", "S")

        actions = play_bot_turn(eng, GreedyBot())

        assert any(action.startswith("discarded ") for action in actions)


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
        ranks = [hand[i].rank for i in idxs]
        assert all(rank == "A" for rank in ranks)

    def test_planner_discard_keeps_wild_when_possible(self):
        hand = [Card("2", "S"), Card("7", "H"), Card("8", "D")]
        idx = PlannerBot().choose_discard_index(hand)
        assert hand[idx].rank != "2"
