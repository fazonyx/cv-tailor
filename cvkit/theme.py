"""Visual theme: palette, page geometry, font sizes.

Everything the renderer needs to know about *looks* lives here, so a fork can
restyle the CV without touching layout or content code.
"""
from dataclasses import dataclass, field, replace

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors

PAGE_W, PAGE_H = A4


def _hex(value):
    return colors.HexColor(value)


@dataclass
class Theme:
    # ── Palette ──────────────────────────────────────────────
    dark: str = "#1A1A2E"          # header band, strong titles
    accent: str = "#E84545"        # section rules, highlights
    accent_soft: str = "#FDECEC"   # tag pills background
    text: str = "#1F2937"          # body text
    muted: str = "#6B7280"         # secondary text
    divider: str = "#D1D5DB"
    sidebar_bg: str = "#F4F5F7"
    box_bg: str = "#F8F9FA"        # experience block background
    link: str = "#2563EB"
    green: str = "#16A34A"
    blue: str = "#2563EB"
    on_dark: str = "#CBD5E1"       # summary lines inside the header band

    # ── Geometry (millimetres unless stated) ─────────────────
    sidebar_w: float = 57.0
    margin_left: float = 12.0
    margin_right: float = 11.0
    gutter: float = 13.0
    header_h: float = 32.0
    bottom_margin_min: float = 15.0   # the "breathing room" rule
    bottom_margin_max: float = 45.0   # past this, the page reads as unfinished

    # ── Type scale (points) ──────────────────────────────────
    font: str = "Helvetica"
    font_bold: str = "Helvetica-Bold"
    font_italic: str = "Helvetica-Oblique"
    size_name: float = 20
    size_headline: float = 8.6
    size_summary: float = 7.4
    size_section: float = 9.0
    size_title: float = 10.0
    size_subtitle: float = 8.4
    size_body: float = 8.3
    size_small: float = 7.4
    leading: float = 1.27          # line height, as a multiple of the font size

    @classmethod
    def from_dict(cls, data):
        if not data:
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown theme keys: {sorted(unknown)}")
        return replace(cls(), **data)

    # Colour accessors return reportlab colours, keeping YAML plain strings.
    def color(self, name):
        return _hex(getattr(self, name))

    def line_height(self, size):
        """Vertical step for a given font size, in points."""
        return size * self.leading

    # ── Derived geometry, in points ──────────────────────────
    @property
    def left_w(self):
        return self.sidebar_w * mm

    @property
    def ml(self):
        return self.margin_left * mm

    @property
    def mr(self):
        return self.margin_right * mm

    @property
    def right_x(self):
        return self.left_w + self.gutter * mm

    @property
    def right_w(self):
        return PAGE_W - self.right_x - self.mr

    @property
    def sidebar_content_w(self):
        return self.left_w - self.ml - 4 * mm
