"""Tests for canasta.bot_ladder."""

from canasta.bot_ladder import LadderSide, run_ladder, simulate_match
from canasta.model import PlayerId


def test_simulate_match_completes_with_winner_and_scores() -> None:
    result = simulate_match(
        north=LadderSide(kind="safe", strength=20),
        south=LadderSide(kind="safe", strength=80),
        seed=7,
        max_rounds=4,
        max_turns_per_round=120,
    )

    assert result.winner in (PlayerId.NORTH, PlayerId.SOUTH)
    assert isinstance(result.north_total, int)
    assert isinstance(result.south_total, int)
    assert result.rounds_played >= 1


def test_run_ladder_aggregates_match_count_and_wins() -> None:
    summary = run_ladder(
        side_a=LadderSide(kind="greedy", strength=25),
        side_b=LadderSide(kind="greedy", strength=85),
        matches=6,
        seed=11,
        swap_seats=True,
        max_rounds=3,
        max_turns_per_round=120,
    )

    assert summary.matches == 6
    assert summary.side_a_wins + summary.side_b_wins + summary.ties == 6


def test_run_ladder_is_deterministic_for_same_seed() -> None:
    summary1 = run_ladder(
        side_a=LadderSide(kind="planner", strength=35),
        side_b=LadderSide(kind="planner", strength=90),
        matches=4,
        seed=19,
        swap_seats=True,
        max_rounds=3,
        max_turns_per_round=120,
    )
    summary2 = run_ladder(
        side_a=LadderSide(kind="planner", strength=35),
        side_b=LadderSide(kind="planner", strength=90),
        matches=4,
        seed=19,
        swap_seats=True,
        max_rounds=3,
        max_turns_per_round=120,
    )

    assert summary1 == summary2