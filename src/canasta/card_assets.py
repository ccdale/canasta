from __future__ import annotations

import os
from pathlib import Path

import platformdirs

from canasta.model import RANKS, Card

_SUIT_BASE_INDEX = {
    "S": 1,
    "H": 14,
    "D": 27,
    "C": 40,
}
_RANK_OFFSET = {rank: idx for idx, rank in enumerate(RANKS)}

# Candidate filenames for the joker image (checked in order).
_JOKER_CANDIDATES = [
    "joker.png",
    "joker.jpg",
    "joker-612x612.jpg",
    "53.png",
]


def asset_dir() -> Path:
    override = os.environ.get("CANASTA_CARD_ASSET_DIR")
    if override:
        return Path(override).expanduser()
    return Path(platformdirs.user_data_dir("canasta"))


def card_image_index(card: Card) -> int | None:
    if card.rank == "JOKER":
        return None
    base = _SUIT_BASE_INDEX.get(card.suit)
    offset = _RANK_OFFSET.get(card.rank)
    if base is None or offset is None:
        return None
    return base + offset


def joker_image_path(base_dir: Path | None = None) -> Path | None:
    """Return the path to the joker image, or None if not found.

    Tries several candidate filenames in the asset directory so that
    different ccacards distributions (PNG or JPEG, various names) are
    supported transparently.
    """
    root = base_dir or asset_dir()
    for name in _JOKER_CANDIDATES:
        path = root / name
        if path.is_file():
            return path
    return None


def card_image_path(card: Card, base_dir: Path | None = None) -> Path | None:
    """Return the filesystem path for a card image, or None if not available.

    Handles jokers via joker_image_path() and regular cards via the
    ccacards 1-52 index scheme (S=1..13, H=14..26, D=27..39, C=40..52).
    """
    if card.rank == "JOKER":
        return joker_image_path(base_dir)
    image_index = card_image_index(card)
    if image_index is None:
        return None
    root = base_dir or asset_dir()
    path = root / f"{image_index}.png"
    return path if path.is_file() else None


def back_image_path(base_dir: Path | None = None) -> Path | None:
    root = base_dir or asset_dir()
    path = root / "back.png"
    return path if path.is_file() else None
