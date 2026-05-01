"""Bootstrap and Python discovery for GTK4 GUI launcher."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

_BOT_CHOICES = ["human", "random", "greedy", "safe", "aggro", "planner"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the GUI."""
    parser = argparse.ArgumentParser(description="Canasta GTK4 GUI")
    parser.add_argument(
        "--assets-dir",
        default=None,
        help="Override card image directory (defaults to XDG data dir or CANASTA_CARD_ASSET_DIR)",
    )
    parser.add_argument(
        "--north",
        choices=_BOT_CHOICES,
        default="random",
        help="Controller for the north seat (default: random)",
    )
    parser.add_argument(
        "--south",
        choices=_BOT_CHOICES,
        default="human",
        help="Controller for the south seat (default: human)",
    )
    parser.add_argument("--bot-seed", type=int, default=0)
    parser.add_argument(
        "--bot-strength",
        type=int,
        default=1,
        help="Bot strength from 1 (baseline) to 100 (strongest)",
    )
    return parser.parse_args(argv)


def python_candidates() -> list[str]:
    """Return list of Python executables to try, in order."""
    candidates = [
        shutil.which("python3"),
        "/usr/bin/python3",
        "/sbin/python3.14",
    ]
    ordered: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in ordered:
            ordered.append(candidate)
    return ordered


def find_python_with_gtk() -> str | None:
    """Find a Python executable that has GTK4 bindings available."""
    check = "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk"
    for candidate in python_candidates():
        result = subprocess.run(
            [candidate, "-c", check],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            return candidate
    return None


def reexec_with_system_python(argv: list[str]) -> int | None:
    """Attempt to re-execute this module with a Python that has GTK4 bindings.

    Returns the exit code if re-execution occurred, or None if it didn't attempt.
    """
    if os.environ.get("CANASTA_GUI_SYSTEM_PYTHON") == "1":
        return None
    candidate = find_python_with_gtk()
    if candidate is None:
        return None

    env = dict(os.environ)
    env["CANASTA_GUI_SYSTEM_PYTHON"] = "1"
    source_root = Path(__file__).resolve().parents[2]
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{source_root}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(source_root)
    )
    result = subprocess.run(
        [candidate, "-m", "canasta.gui", *argv],
        env=env,
        check=False,
    )
    return result.returncode
