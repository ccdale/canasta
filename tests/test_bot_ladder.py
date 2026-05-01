"""Tests for canasta.bot_ladder."""

import json

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


def test_cli_accepts_compact_side_specs(capsys) -> None:
    from canasta.bot_ladder import main

    code = main(
        [
            "safe:30",
            "safe:80",
            "-m",
            "2",
            "-s",
            "3",
            "--max-rounds",
            "2",
            "--max-turns-per-round",
            "80",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert "Ladder: safe:30 vs safe:80" in captured.out


def test_cli_accepts_json_config_file(tmp_path, capsys) -> None:
    from canasta.bot_ladder import main

    config = {
        "side_a": "greedy:25",
        "side_b": {"kind": "greedy", "strength": 90},
        "matches": 2,
        "seed": 5,
        "max_rounds": 2,
        "max_turns_per_round": 80,
        "swap_seats": False,
    }
    config_path = tmp_path / "ladder.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    code = main(["--config", str(config_path)])
    captured = capsys.readouterr()

    assert code == 0
    assert "Ladder: greedy:25 vs greedy:90" in captured.out
    assert "swap seats: False" in captured.out


def test_cli_lists_presets(capsys) -> None:
    from canasta.bot_ladder import main

    code = main(["--list-presets"])
    captured = capsys.readouterr()

    assert code == 0
    assert "Available presets:" in captured.out
    assert "safe-30v80" in captured.out


def test_cli_accepts_named_preset(capsys) -> None:
    from canasta.bot_ladder import main

    code = main(
        [
            "--preset",
            "safe-30v80",
            "-m",
            "2",
            "-s",
            "2",
            "--max-rounds",
            "2",
            "--max-turns-per-round",
            "80",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert "Ladder: safe:30 vs safe:80" in captured.out


def test_cli_writes_csv_summary(tmp_path, capsys) -> None:
    from canasta.bot_ladder import main

    csv_path = tmp_path / "results" / "ladder.csv"
    code = main(
        [
            "safe:30",
            "safe:80",
            "-m",
            "2",
            "-s",
            "5",
            "--max-rounds",
            "2",
            "--max-turns-per-round",
            "80",
            "--csv",
            str(csv_path),
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert csv_path.exists()
    rows = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 2
    assert rows[0].startswith("side_a_kind,side_a_strength")
    assert ",safe,30,safe,80," in f",{rows[1]},"
    assert "CSV written:" in captured.out
