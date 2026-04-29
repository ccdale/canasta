from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path


def _git_root() -> Path | None:
    """Return the git repository root, or None if unavailable."""
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    except Exception:
        return None
    return Path(root)


def get_version() -> str:
    """Get project version from pyproject.toml, falling back safely."""
    root = _git_root()
    if root is not None:
        pyproject_path = root / "pyproject.toml"
    else:
        pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"

    if pyproject_path.exists():
        try:
            with open(pyproject_path, "rb") as file_obj:
                data = tomllib.load(file_obj)
            return data.get("project", {}).get("version", "0.0.0")
        except Exception:
            return "0.0.0"
    return "0.0.0"


__version__ = get_version()

__all__ = ["__version__", "get_version"]
