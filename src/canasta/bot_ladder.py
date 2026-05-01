"""Bot-vs-bot ladder harness for strength benchmarking."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class LadderPreset:
    name: str
    side_a: LadderSide
    side_b: LadderSide
    description: str


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
            bot = (
                north_bot
                if engine.state.current_player == PlayerId.NORTH
                else south_bot
            )
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
    parser.add_argument(
        "side_a",
        nargs="?",
        help="Optional shorthand side A spec in the form kind:strength (example: safe:30)",
    )
    parser.add_argument(
        "side_b",
        nargs="?",
        help="Optional shorthand side B spec in the form kind:strength (example: safe:80)",
    )
    parser.add_argument(
        "--side-a-kind", "-ak", default=None, choices=_bot_kind_choices()
    )
    parser.add_argument("--side-a-strength", "-as", type=int, default=None)
    parser.add_argument(
        "--side-b-kind", "-bk", default=None, choices=_bot_kind_choices()
    )
    parser.add_argument("--side-b-strength", "-bs", type=int, default=None)
    parser.add_argument("--config", "-c", help="JSON config file for ladder options")
    parser.add_argument(
        "--preset",
        "-p",
        choices=sorted(_preset_definitions().keys()),
        help="Named matchup preset (reduces typing for common runs)",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List preset names and exit",
    )
    parser.add_argument("--matches", "-m", type=int, default=20)
    parser.add_argument("--seed", "-s", type=int, default=1)
    parser.add_argument(
        "--csv",
        help="Write one-row ladder summary to CSV file",
    )
    parser.add_argument("--no-swap-seats", action="store_true")
    parser.add_argument("--max-rounds", type=int, default=16)
    parser.add_argument("--max-turns-per-round", type=int, default=400)
    return parser


def _bot_kind_choices() -> list[str]:
    return ["random", "greedy", "safe", "aggro", "planner"]


def _validate_positive(parser: argparse.ArgumentParser, value: int, name: str) -> None:
    if value <= 0:
        parser.error(f"{name} must be greater than 0")


def _validate_strength(parser: argparse.ArgumentParser, value: int, name: str) -> None:
    if value < 1 or value > 100:
        parser.error(f"{name} must be between 1 and 100")


def _parse_side_spec(
    parser: argparse.ArgumentParser, value: str, name: str
) -> LadderSide:
    if ":" not in value:
        parser.error(f"{name} must be in kind:strength format (example: safe:30)")
    kind_part, strength_part = value.split(":", 1)
    kind = kind_part.strip().lower()
    if kind not in _bot_kind_choices():
        parser.error(f"{name} kind must be one of: {', '.join(_bot_kind_choices())}")
    try:
        strength = int(strength_part)
    except ValueError:
        parser.error(f"{name} strength must be an integer")
    _validate_strength(parser, strength, f"{name} strength")
    return LadderSide(kind=kind, strength=strength)


def _preset_definitions() -> dict[str, LadderPreset]:
    return {
        "safe-30v80": LadderPreset(
            name="safe-30v80",
            side_a=LadderSide(kind="safe", strength=30),
            side_b=LadderSide(kind="safe", strength=80),
            description="Safe bot strength progression check",
        ),
        "safe-50v90": LadderPreset(
            name="safe-50v90",
            side_a=LadderSide(kind="safe", strength=50),
            side_b=LadderSide(kind="safe", strength=90),
            description="Safe bot higher-tier gap check",
        ),
        "greedy-30v80": LadderPreset(
            name="greedy-30v80",
            side_a=LadderSide(kind="greedy", strength=30),
            side_b=LadderSide(kind="greedy", strength=80),
            description="Greedy bot strength progression check",
        ),
        "planner-40v90": LadderPreset(
            name="planner-40v90",
            side_a=LadderSide(kind="planner", strength=40),
            side_b=LadderSide(kind="planner", strength=90),
            description="Planner bot strength progression check",
        ),
        "aggro-30v80": LadderPreset(
            name="aggro-30v80",
            side_a=LadderSide(kind="aggro", strength=30),
            side_b=LadderSide(kind="aggro", strength=80),
            description="Aggro bot strength progression check",
        ),
    }


def _load_json_config(
    parser: argparse.ArgumentParser, config_path: str
) -> dict[str, object]:
    path = Path(config_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        parser.error(f"could not read config file {config_path}: {exc}")

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        parser.error(f"invalid JSON in config file {config_path}: {exc}")

    if not isinstance(loaded, dict):
        parser.error("config root must be a JSON object")
    return loaded


def _resolve_side(
    parser: argparse.ArgumentParser,
    cli_spec: str | None,
    cli_kind: str | None,
    cli_strength: int | None,
    cfg: dict[str, object],
    cfg_key: str,
    side_name: str,
    preset_side: LadderSide | None,
    default_side: LadderSide,
) -> LadderSide:
    if cli_spec:
        return _parse_side_spec(parser, cli_spec, side_name)

    cfg_entry = cfg.get(cfg_key)
    if isinstance(cfg_entry, str):
        return _parse_side_spec(parser, cfg_entry, side_name)

    if isinstance(cfg_entry, dict):
        kind_obj = cfg_entry.get("kind")
        strength_obj = cfg_entry.get("strength")
        if not isinstance(kind_obj, str):
            parser.error(f"{cfg_key}.kind in config must be a string")
        if not isinstance(strength_obj, int):
            parser.error(f"{cfg_key}.strength in config must be an integer")
        kind = kind_obj.lower()
        if kind not in _bot_kind_choices():
            parser.error(
                f"{cfg_key}.kind must be one of: {', '.join(_bot_kind_choices())}"
            )
        _validate_strength(parser, strength_obj, f"{cfg_key}.strength")
        return LadderSide(kind=kind, strength=strength_obj)

    if cli_kind is not None or cli_strength is not None:
        kind = cli_kind if cli_kind is not None else default_side.kind
        strength = cli_strength if cli_strength is not None else default_side.strength
        _validate_strength(parser, strength, side_name)
        return LadderSide(kind=kind, strength=strength)

    if preset_side is not None:
        return preset_side

    return default_side


def _write_csv_summary(
    csv_path: str,
    side_a: LadderSide,
    side_b: LadderSide,
    summary: LadderResult,
    matches: int,
    seed: int,
    swap_seats: bool,
    max_rounds: int,
    max_turns_per_round: int,
) -> None:
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "side_a_kind",
                "side_a_strength",
                "side_b_kind",
                "side_b_strength",
                "matches",
                "seed",
                "swap_seats",
                "max_rounds",
                "max_turns_per_round",
                "side_a_wins",
                "side_b_wins",
                "ties",
                "side_a_avg_total",
                "side_b_avg_total",
                "stalled_rounds",
            ]
        )
        writer.writerow(
            [
                side_a.kind,
                side_a.strength,
                side_b.kind,
                side_b.strength,
                matches,
                seed,
                swap_seats,
                max_rounds,
                max_turns_per_round,
                summary.side_a_wins,
                summary.side_b_wins,
                summary.ties,
                f"{summary.side_a_avg_total:.3f}",
                f"{summary.side_b_avg_total:.3f}",
                summary.stalled_rounds,
            ]
        )


def _print_presets() -> None:
    print("Available presets:")
    for preset in _preset_definitions().values():
        print(
            f"  {preset.name}: {preset.side_a.kind}:{preset.side_a.strength} vs "
            f"{preset.side_b.kind}:{preset.side_b.strength} ({preset.description})"
        )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list_presets:
        _print_presets()
        return 0

    config: dict[str, object] = {}
    if args.config:
        config = _load_json_config(parser, args.config)

    if args.preset is None:
        config_preset = config.get("preset")
        if isinstance(config_preset, str):
            if config_preset not in _preset_definitions():
                parser.error(
                    f"config preset must be one of: {', '.join(sorted(_preset_definitions()))}"
                )
            args.preset = config_preset

    config_matches = config.get("matches")
    if isinstance(config_matches, int):
        args.matches = config_matches
    config_seed = config.get("seed")
    if isinstance(config_seed, int):
        args.seed = config_seed
    config_max_rounds = config.get("max_rounds")
    if isinstance(config_max_rounds, int):
        args.max_rounds = config_max_rounds
    config_max_turns = config.get("max_turns_per_round")
    if isinstance(config_max_turns, int):
        args.max_turns_per_round = config_max_turns
    config_swap = config.get("swap_seats")
    if isinstance(config_swap, bool):
        args.no_swap_seats = not config_swap
    config_csv = config.get("csv")
    if args.csv is None and isinstance(config_csv, str):
        args.csv = config_csv

    preset = _preset_definitions().get(args.preset) if args.preset else None

    _validate_positive(parser, args.matches, "--matches")
    _validate_positive(parser, args.max_rounds, "--max-rounds")
    _validate_positive(parser, args.max_turns_per_round, "--max-turns-per-round")

    side_a = _resolve_side(
        parser=parser,
        cli_spec=args.side_a,
        cli_kind=args.side_a_kind,
        cli_strength=args.side_a_strength,
        cfg=config,
        cfg_key="side_a",
        side_name="side_a",
        preset_side=preset.side_a if preset else None,
        default_side=LadderSide(kind="safe", strength=30),
    )
    side_b = _resolve_side(
        parser=parser,
        cli_spec=args.side_b,
        cli_kind=args.side_b_kind,
        cli_strength=args.side_b_strength,
        cfg=config,
        cfg_key="side_b",
        side_name="side_b",
        preset_side=preset.side_b if preset else None,
        default_side=LadderSide(kind="safe", strength=80),
    )
    summary = run_ladder(
        side_a=side_a,
        side_b=side_b,
        matches=args.matches,
        seed=args.seed,
        swap_seats=not args.no_swap_seats,
        max_rounds=args.max_rounds,
        max_turns_per_round=args.max_turns_per_round,
    )

    side_a_desc = f"{side_a.kind}:{side_a.strength}"
    side_b_desc = f"{side_b.kind}:{side_b.strength}"
    print(f"Ladder: {side_a_desc} vs {side_b_desc}")
    print(f"Matches: {summary.matches} (swap seats: {not args.no_swap_seats})")
    print(
        f"Wins: side A {summary.side_a_wins} | side B {summary.side_b_wins} | ties {summary.ties}"
    )
    print(
        f"Avg total score: side A {summary.side_a_avg_total:.1f} | side B {summary.side_b_avg_total:.1f}"
    )
    print(f"Stalled rounds resolved: {summary.stalled_rounds}")

    if args.csv:
        _write_csv_summary(
            csv_path=args.csv,
            side_a=side_a,
            side_b=side_b,
            summary=summary,
            matches=args.matches,
            seed=args.seed,
            swap_seats=not args.no_swap_seats,
            max_rounds=args.max_rounds,
            max_turns_per_round=args.max_turns_per_round,
        )
        print(f"CSV written: {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
