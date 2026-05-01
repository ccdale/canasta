"""CSS theme for the Canasta GTK window."""

from __future__ import annotations

# Green-felt table CSS matching patience/ui/theme.py style.
TABLE_CSS = """
@media (prefers-color-scheme: light) {
    .table-window {
        background-color: #dce6d7;
        background-image: linear-gradient(180deg, #edf3e9 0%, #dfe9d9 38%, #d3e0cd 100%);
    }
}
@media (prefers-color-scheme: dark) {
    .table-window {
        background-color: #132219;
        background-image: linear-gradient(180deg, #1b2d22 0%, #14251b 42%, #0e1b14 100%);
    }
}
.section-label { font-weight: bold; }
.hand-card {
    padding: 2px;
    min-width: 0;
    min-height: 0;
}
.draw-preview-new {
    border: 2px solid #f4b400;
    border-radius: 8px;
}
.canasta-card-shell {
    border: 2px solid #d4af37;
    border-radius: 8px;
    padding: 2px;
}
"""

Gtk = None
Gdk = None


def set_gtk_imports(gtk, gdk) -> None:
    """Set the deferred GTK/GDK imports used for CSS installation."""
    global Gtk, Gdk
    Gtk = gtk
    Gdk = gdk


def install_css() -> None:
    """Install the table CSS theme into the default GTK display."""
    display = Gdk.Display.get_default()
    if display is None:
        return
    provider = Gtk.CssProvider()
    provider.load_from_string(TABLE_CSS)
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
