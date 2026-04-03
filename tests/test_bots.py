"""Tests for canasta.bots."""

from canasta.bots import GreedyBot, RandomBot, build_bot, play_bot_turn
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
