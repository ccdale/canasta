"""Bot-vs-bot ladder harness for strength benchmarking."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from canasta.bots import BotKind, build_bot, play_bot_turn
from canasta.engine import CanastaEngine
from canasta.model import PlayerId, RuleError
from canasta.scoring import calculate_round_score


@dataclass(frozen=True)
class LadderSide:
    kind: BotKind
    strength: int


@dataclass(frozen=True)
class MatchResult:
    winner: PlayerId
    north_total: int
    south_total: int
    rounds_played: int
    stalled_rounds: int


@dataclass(frozen=True)
class LadderResult:
    matches: int
    side_a_wins: int
    side_b_wins: int
    ties: int
    side_a_avg_total: float
    side_b_avg_total: float
    stalled_rounds: int


def simulate_match(
    north: LadderSide,
    south: LadderSide,
    seed: int,
    max_rounds: int = 16,
    max_turns_per_round: int = 400,
) -> MatchResult:
    """Simulate a full match with guardrails for stalled rounds.

    Bots only draw from stock and do not currently attempt discard pickup. That can
    produce stalled rounds when stock is too low to draw. In that case we force-round
    resolution using total score projections with hand penalties included.
    """
    engine = CanastaEngine(seed=seed)
    north_bot = build_bot(north.kind, seed=seed + 101, strength=north.strength)
    south_bot = build_bot(south.kind, seed=seed + 202, strength=south.strength)
    stalled_rounds = 0

    while engine.match_winner() is None and engine.state.round_number <= max_rounds:
        turns = 0
        while engine.state.winner is None and turns < max_turns_per_round:
            bot = north_bot if engine.state.current_player == PlayerId.NORTH else south_bot
            try:
                play_bot_turn(engine, bot)
            except RuleError:
                _resolve_stalled_round(engine)
                stalled_rounds += 1
                break
            turns += 1

        if engine.state.winner is None:
            _resolve_stalled_round(engine)
            stalled_rounds += 1

        if engine.match_winner() is not None:
            break

        engine.next_round()

    winner = engine.match_winner()
    north_total = engine.total_score(PlayerId.NORTH)
    south_total = engine.total_score(PlayerId.SOUTH)
    if winner is None:
        winner = PlayerId.NORTH if north_total >= south_total else PlayerId.SOUTH

    return MatchResult(
        winner=winner,
        north_total=north_total,
        south_total=south_total,
        rounds_played=engine.state.round_number,
        stalled_rounds=stalled_rounds,
    )


def run_ladder(
    side_a: LadderSide,
    side_b: LadderSide,
    matches: int,
    seed: int = 1,
    swap_seats: bool = True,
    max_rounds: int = 16,
    max_turns_per_round: int = 400,
) -> LadderResult:
    """Run a repeated ladder and aggregate wins and average totals."""
    side_a_wins = 0
    side_b_wins = 0
    ties = 0
    side_a_total_sum = 0
    side_b_total_sum = 0
    stalled_rounds = 0

    for match_idx in range(matches):
        if swap_seats and match_idx % 2 == 1:
            north_side = side_b
            south_side = side_a
            side_a_is_north = False
        else:
            north_side = side_a
            south_side = side_b
            side_a_is_north = True

        result = simulate_match(
            north=north_side,
            south=south_side,
            seed=seed + match_idx,
            max_rounds=max_rounds,
            max_turns_per_round=max_turns_per_round,
        )
        stalled_rounds += result.stalled_rounds

        if side_a_is_north:
            side_a_total = result.north_total
            side_b_total = result.south_total
            side_a_won = result.winner == PlayerId.NORTH
            side_b_won = result.winner == PlayerId.SOUTH
        else:
            side_a_total = result.south_total
            side_b_total = result.north_total
            side_a_won = result.winner == PlayerId.SOUTH
            side_b_won = result.winner == PlayerId.NORTH

        side_a_total_sum += side_a_total
        side_b_total_sum += side_b_total

        if side_a_won and not side_b_won:
            side_a_wins += 1
        elif side_b_won and not side_a_won:
            side_b_wins += 1
        else:
            ties += 1

    if matches == 0:
        return LadderResult(
            matches=0,
            side_a_wins=0,
            side_b_wins=0,
            ties=0,
            side_a_avg_total=0.0,
            side_b_avg_total=0.0,
            stalled_rounds=0,
        )

    return LadderResult(
        matches=matches,
        side_a_wins=side_a_wins,
        side_b_wins=side_b_wins,
        ties=ties,
        side_a_avg_total=side_a_total_sum / matches,
        side_b_avg_total=side_b_total_sum / matches,
        stalled_rounds=stalled_rounds,
    )


def _resolve_stalled_round(engine: CanastaEngine) -> None:
    """Force round completion by projected total score with hand penalties."""
    if engine.state.winner is not None:
        return

    projected_totals: dict[PlayerId, int] = {}
    for player_id in (PlayerId.NORTH, PlayerId.SOUTH):
        player = engine.state.players[player_id]
        round_score = calculate_round_score(player, round_over=True)
        projected_totals[player_id] = player.score + round_score

    if projected_totals[PlayerId.NORTH] > projected_totals[PlayerId.SOUTH]:
        engine.state.winner = PlayerId.NORTH
    elif projected_totals[PlayerId.SOUTH] > projected_totals[PlayerId.NORTH]:
        engine.state.winner = PlayerId.SOUTH
    else:
        # Deterministic tie-break for repeatable simulations.
        engine.state.winner = engine.state.current_player


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Canasta bot-vs-bot ladder")
    parser.add_argument("--side-a-kind", default="safe", choices=_bot_kind_choices())
    parser.add_argument("--side-a-strength", type=int, default=30)
    parser.add_argument("--side-b-kind", default="safe", choices=_bot_kind_choices())
    parser.add_argument("--side-b-strength", type=int, default=80)
    parser.add_argument("--matches", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--no-swap-seats", action="store_true")
    parser.add_argument("--max-rounds", type=int, default=16)
    parser.add_argument("--max-turns-per-round", type=int, default=400)
    return parser


def _bot_kind_choices() -> list[str]:
    return ["random", "greedy", "safe", "aggro", "planner"]


def _validate_positive(parser: argparse.ArgumentParser, value: int, name: str) -> None:
    if value <= 0:
        parser.error(f"{name} must be greater than 0")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _validate_positive(parser, args.matches, "--matches")
    _validate_positive(parser, args.max_rounds, "--max-rounds")
    _validate_positive(parser, args.max_turns_per_round, "--max-turns-per-round")

    side_a = LadderSide(kind=args.side_a_kind, strength=args.side_a_strength)
    side_b = LadderSide(kind=args.side_b_kind, strength=args.side_b_strength)
    summary = run_ladder(
        side_a=side_a,
        side_b=side_b,
        matches=args.matches,
        seed=args.seed,
        swap_seats=not args.no_swap_seats,
        max_rounds=args.max_rounds,
        max_turns_per_round=args.max_turns_per_round,
    )

    side_a_desc = f"{args.side_a_kind}:{args.side_a_strength}"
    side_b_desc = f"{args.side_b_kind}:{args.side_b_strength}"
    print(f"Ladder: {side_a_desc} vs {side_b_desc}")
    print(f"Matches: {summary.matches} (swap seats: {not args.no_swap_seats})")
    print(f"Wins: side A {summary.side_a_wins} | side B {summary.side_b_wins} | ties {summary.ties}")
    print(f"Avg total score: side A {summary.side_a_avg_total:.1f} | side B {summary.side_b_avg_total:.1f}")
    print(f"Stalled rounds resolved: {summary.stalled_rounds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())