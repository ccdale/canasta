"""GTK4 widget builders for cards and piles."""

from __future__ import annotations

from pathlib import Path

from canasta.card_assets import card_image_path
from canasta.model import Card

# These will be imported from gi.repository by the main() function
# when GTK is available. For type hints, we keep them as forward references.
Gtk = None
Gdk = None
GdkPixbuf = None


def set_gtk_imports(gtk, gdk, gdk_pixbuf):
    """Set the GTK imports for use by widget builders.

    Called from main() after importing gi.repository modules.
    """
    global Gtk, Gdk, GdkPixbuf
    Gtk = gtk
    Gdk = gdk
    GdkPixbuf = gdk_pixbuf


# Constants for card display
CARD_W = 71
CARD_H = 100
CARD_PEEK = 22  # pixels of left edge visible per card in the fan layout
CARD_LIFT = 10  # pixels a selected card is raised above the row
MELD_PEEK = 18  # tighter fan so meld groups consume less horizontal space


def build_card_picture(image_path: Path) -> object:  # Gtk.Widget
    """Build a picture widget from a card image file."""
    picture = Gtk.Picture.new_for_filename(str(image_path))
    picture.set_content_fit(Gtk.ContentFit.FILL)
    picture.set_can_shrink(True)
    picture.set_size_request(CARD_W, CARD_H)
    picture.set_halign(Gtk.Align.START)
    picture.set_valign(Gtk.Align.START)
    picture.set_hexpand(False)
    picture.set_vexpand(False)

    wrapper = Gtk.Box()
    wrapper.set_size_request(CARD_W, CARD_H)
    wrapper.set_halign(Gtk.Align.START)
    wrapper.set_valign(Gtk.Align.START)
    wrapper.set_hexpand(False)
    wrapper.set_vexpand(False)
    wrapper.append(picture)
    return wrapper


def build_card_widget(
    card: Card, assets_root: Path, format_func
) -> object:  # Gtk.Widget
    """Build a card widget with image or text fallback."""
    path = card_image_path(card, assets_root)
    if path is not None:
        return build_card_picture(path)
    fallback = Gtk.Box()
    fallback.set_size_request(CARD_W, CARD_H)
    label = Gtk.Label(label=format_func(card))
    label.set_wrap(True)
    fallback.append(label)
    return fallback


def build_fanned_cards(
    cards: list[Card], assets_root: Path, format_func, peek: int = MELD_PEEK
) -> object:  # Gtk.Widget
    """Build a fanned card display."""
    fan = Gtk.Fixed()
    n_cards = len(cards)
    total_w = max(CARD_W, (n_cards - 1) * peek + CARD_W) if n_cards else CARD_W
    fan.set_size_request(total_w, CARD_H + 4)
    for idx, card in enumerate(cards):
        fan.put(build_card_widget(card, assets_root, format_func), idx * peek, 2)
    return fan


def build_pile_picture(image_path: Path) -> object:  # Gtk.Widget
    """Build a stock/discard pile widget with fixed size."""
    # Stock/discard must stay fixed-size regardless of parent row allocation.
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(image_path), CARD_W, CARD_H, False
        )
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        picture = Gtk.Picture.new_for_paintable(texture)
    except Exception:
        picture = Gtk.Picture()
    picture.set_content_fit(Gtk.ContentFit.FILL)
    picture.set_can_shrink(True)
    picture.set_size_request(CARD_W, CARD_H)
    picture.set_halign(Gtk.Align.START)
    picture.set_valign(Gtk.Align.START)
    picture.set_hexpand(False)
    picture.set_vexpand(False)
    return picture
