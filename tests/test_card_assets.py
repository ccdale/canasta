from pathlib import Path

from canasta.card_assets import (
    asset_dir,
    back_image_path,
    card_image_index,
    card_image_path,
)
from canasta.model import Card


def test_card_image_index_maps_spades() -> None:
    assert card_image_index(Card("A", "S")) == 1
    assert card_image_index(Card("K", "S")) == 13


def test_card_image_index_maps_other_suits() -> None:
    assert card_image_index(Card("A", "H")) == 14
    assert card_image_index(Card("A", "D")) == 27
    assert card_image_index(Card("A", "C")) == 40


def test_card_image_index_returns_none_for_joker() -> None:
    assert card_image_index(Card("JOKER")) is None


def test_asset_dir_uses_override(monkeypatch) -> None:
    monkeypatch.setenv("CANASTA_CARD_ASSET_DIR", "/tmp/canasta-assets")
    assert asset_dir() == Path("/tmp/canasta-assets")


def test_card_image_path_returns_existing_path(tmp_path: Path) -> None:
    image = tmp_path / "1.png"
    image.write_text("x")
    assert card_image_path(Card("A", "S"), tmp_path) == image


def test_back_image_path_returns_existing_path(tmp_path: Path) -> None:
    image = tmp_path / "back.png"
    image.write_text("x")
    assert back_image_path(tmp_path) == image


def test_joker_image_path_finds_jpg_variant(tmp_path: Path) -> None:
    from canasta.card_assets import joker_image_path

    image = tmp_path / "joker-612x612.jpg"
    image.write_text("x")
    assert joker_image_path(tmp_path) == image


def test_joker_image_path_prefers_png_over_jpg(tmp_path: Path) -> None:
    from canasta.card_assets import joker_image_path

    jpg = tmp_path / "joker-612x612.jpg"
    jpg.write_text("x")
    png = tmp_path / "joker.png"
    png.write_text("x")
    assert joker_image_path(tmp_path) == png


def test_card_image_path_joker_delegates_to_joker_path(tmp_path: Path) -> None:
    image = tmp_path / "joker.png"
    image.write_text("x")
    assert card_image_path(Card("JOKER"), tmp_path) == image


def test_joker_image_path_returns_none_when_missing(tmp_path: Path) -> None:
    from canasta.card_assets import joker_image_path

    assert joker_image_path(tmp_path) is None
