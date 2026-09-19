"""Drawing primitives - a thin, opinionated layer over a ReportLab canvas.

This module knows about *shapes* (header band, experience block, skill row,
language bar). It knows nothing about YAML, profiles or job offers: feed it
plain strings and it draws them. Two cursors are kept, one per column, so
blocks stack naturally and the renderer never computes coordinates by hand.

Block heights are always derived from the content that goes in them.
Hard-coded box heights are the usual reason a generated CV silently overflows.
"""
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from .theme import PAGE_H, PAGE_W, Theme

BULLET = "•"
WHITE = colors.white


class CVCanvas:
    def __init__(self, path, theme=None, title=None, author=None):
        self.theme = theme or Theme()
        self.c = rl_canvas.Canvas(path, pagesize=(PAGE_W, PAGE_H))
        if title:
            self.c.setTitle(title)
        if author:
            self.c.setAuthor(author)
        self.y_left = 0.0
        self.y_right = 0.0
        self._header_h = 0.0

    # ---- helpers -------------------------------------------------
    def wrap(self, text, font, size, max_w):
        """Greedy word wrap against real glyph widths."""
        words = str(text).split()
        lines, cur = [], ""
        for word in words:
            probe = (cur + " " + word).strip()
            if not cur or self.c.stringWidth(probe, font, size) <= max_w:
                cur = probe
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines or [""]

    def _text(self, x, y, text, font, size, color):
        self.c.setFont(font, size)
        self.c.setFillColor(self.theme.color(color) if isinstance(color, str) else color)
        self.c.drawString(x, y, str(text))

    def _text_right(self, x_right, y, text, font, size, color):
        self.c.setFont(font, size)
        self.c.setFillColor(self.theme.color(color) if isinstance(color, str) else color)
        self.c.drawRightString(x_right, y, str(text))

    def link(self, x, y, label, url, size=None, color="link"):
        size = size or self.theme.size_small
        self._text(x, y, label, self.theme.font, size, color)
        width = self.c.stringWidth(label, self.theme.font, size)
        self.c.linkURL(url, (x, y - 1, x + width, y + size), relative=0)
        return width

    # ---- page lifecycle ------------------------------------------
    def start_page(self, header_h=None):
        theme = self.theme
        height = (header_h or theme.header_h) * mm
        self._header_h = height
        self.y_left = PAGE_H - height - 8 * mm
        self.y_right = PAGE_H - height - 8 * mm
        return height

    def sidebar_background(self):
        theme = self.theme
        self.c.setFillColor(theme.color("sidebar_bg"))
        self.c.rect(0, 0, theme.left_w, PAGE_H - self._header_h, fill=1, stroke=0)
        self.c.setStrokeColor(theme.color("divider"))
        self.c.setLineWidth(0.5)
        self.c.line(theme.left_w, 8 * mm, theme.left_w, PAGE_H - self._header_h)

    def end_page(self):
        self.c.showPage()

    def save(self):
        self.c.save()

    def margins_mm(self):
        """Remaining white space under each column, in millimetres."""
        return (self.y_left / mm, self.y_right / mm)

    # ---- header band ---------------------------------------------
    def header(self, name, headline=None, summary=(), height=None):
        theme = self.theme
        band = self.start_page(height)
        self.c.setFillColor(theme.color("dark"))
        self.c.rect(0, PAGE_H - band, PAGE_W, band, fill=1, stroke=0)
        self.c.setFillColor(theme.color("accent"))
        self.c.rect(0, PAGE_H - band, 5, band, fill=1, stroke=0)

        x = theme.ml + 6
        y = PAGE_H - 10 * mm
        self._text(x, y, name, theme.font_bold, theme.size_name, WHITE)
        y -= 5.5 * mm
        if headline:
            self._text(x, y, headline, theme.font_bold, theme.size_headline, "accent")
            y -= 4.5 * mm
        width = PAGE_W - x - theme.mr
        for entry in summary:
            for line in self.wrap(entry, theme.font, theme.size_summary, width):
                self._text(x, y, line, theme.font, theme.size_summary, "on_dark")
                y -= 4 * mm
        return band

    # ---- right column --------------------------------------------
    def section(self, label):
        theme = self.theme
        y = self.y_right
        self._text(theme.right_x, y, label.upper(), theme.font_bold,
                   theme.size_section, "accent")
        width = self.c.stringWidth(label.upper(), theme.font_bold, theme.size_section)
        self.c.setStrokeColor(theme.color("accent"))
        self.c.setLineWidth(0.9)
        self.c.line(theme.right_x + width + 4, y + 2.5, PAGE_W - theme.mr, y + 2.5)
        self.y_right = y - 6 * mm

    def employer_bar(self, employer, role=None, period=None):
        """Dark band naming the employer, above one or more client missions.

        Consultants need this: the employer and contract title stay factual on
        the band, while each client mission below can be framed for the offer.
        """
        theme = self.theme
        height = 6.5 * mm
        y = self.y_right - height + 4.5 * mm
        self.c.setFillColor(theme.color("dark"))
        self.c.rect(theme.right_x, y - 1.5 * mm, theme.right_w, height, fill=1, stroke=0)
        self._text(theme.right_x + 2.5 * mm, y, employer, theme.font_bold,
                   theme.size_subtitle + 0.5, WHITE)
        if role:
            width = self.c.stringWidth(employer, theme.font_bold, theme.size_subtitle + 0.5)
            self._text(theme.right_x + 3.5 * mm + width, y, role, theme.font,
                       theme.size_small, "on_dark")
        if period:
            self._text_right(PAGE_W - theme.mr - 2.5 * mm, y, period,
                             theme.font_bold, theme.size_small, "on_dark")
        self.y_right -= height + 1.5 * mm

    def _experience_height(self, subtitle, bullets, env, tags):
        theme = self.theme
        inner_w = theme.right_w - 9.5 * mm
        body_lh = theme.line_height(theme.size_body)
        small_lh = theme.line_height(theme.size_small)
        height = theme.line_height(theme.size_title) + 0.5 * mm
        if subtitle:
            height += theme.line_height(theme.size_subtitle) + 0.4 * mm
        if tags:
            height += 4.0 * mm
        for bullet in bullets:
            height += body_lh * len(self.wrap(bullet, theme.font, theme.size_body, inner_w))
        if env:
            height += 1.0 * mm
            height += small_lh * len(self.wrap("Env. " + env, theme.font_italic,
                                               theme.size_small, theme.right_w - 6 * mm))
        return height + 2.5 * mm

    def experience(self, title, subtitle=None, period=None, bullets=(), env=None,
                   tags=(), boxed=True):
        theme = self.theme
        height = self._experience_height(subtitle, bullets, env, tags)
        top = self.y_right
        if boxed:
            self.c.setFillColor(theme.color("box_bg"))
            self.c.rect(theme.right_x, top - height + 4 * mm, theme.right_w, height,
                        fill=1, stroke=0)
            self.c.setFillColor(theme.color("accent"))
            self.c.rect(theme.right_x, top - height + 4 * mm, 1.6, height, fill=1, stroke=0)

        x = theme.right_x + 3 * mm
        y = top
        self._text(x, y, title, theme.font_bold, theme.size_title, "dark")
        if period:
            self._text_right(PAGE_W - theme.mr - 2 * mm, y, period, theme.font_bold,
                             theme.size_small, "muted")
        y -= theme.line_height(theme.size_title)
        if subtitle:
            self._text(x, y, subtitle, theme.font, theme.size_subtitle, "accent")
            y -= theme.line_height(theme.size_subtitle) + 0.4 * mm
        if tags:
            self.tags(x, y, tags)
            y -= 4.0 * mm
        inner_w = theme.right_w - 9.5 * mm
        for bullet in bullets:
            self._text(x, y, BULLET, theme.font_bold, theme.size_body, "accent")
            for line in self.wrap(bullet, theme.font, theme.size_body, inner_w):
                self._text(x + 3.2 * mm, y, line, theme.font, theme.size_body, "text")
                y -= theme.line_height(theme.size_body)
        if env:
            y -= 1.0 * mm
            for line in self.wrap("Env. " + env, theme.font_italic, theme.size_small,
                                  theme.right_w - 6 * mm):
                self._text(x, y, line, theme.font_italic, theme.size_small, "muted")
                y -= theme.line_height(theme.size_small)
        self.y_right = top - height - 1.5 * mm

    def tags(self, x, y, labels):
        theme = self.theme
        for label in labels:
            width = self.c.stringWidth(label, theme.font_bold, 6.2) + 4 * mm
            self.c.setFillColor(theme.color("accent_soft"))
            self.c.roundRect(x, y - 1.2 * mm, width, 3.9 * mm, 1.2 * mm, fill=1, stroke=0)
            self._text(x + 2 * mm, y, label, theme.font_bold, 6.2, "accent")
            x += width + 1.5 * mm

    def skill_row(self, label, value):
        theme = self.theme
        y = self.y_right
        self._text(theme.right_x, y, label, theme.font_bold, theme.size_body, "dark")
        # A long label (they get longer once translated) pushes the value
        # right instead of being overprinted by it.
        label_w = max(26 * mm,
                      self.c.stringWidth(label, theme.font_bold, theme.size_body) + 3 * mm)
        for line in self.wrap(value, theme.font, theme.size_body, theme.right_w - label_w):
            self._text(theme.right_x + label_w, y, line, theme.font, theme.size_body, "text")
            y -= theme.line_height(theme.size_body)
        self.y_right = y - 0.8 * mm

    def education(self, years, school, degree=None, detail=None):
        theme = self.theme
        y = self.y_right
        self._text(theme.right_x, y, years, theme.font_bold, theme.size_body, "accent")
        self._text(theme.right_x + 18 * mm, y, school, theme.font_bold,
                   theme.size_body, "dark")
        if degree:
            self._text_right(PAGE_W - theme.mr, y, degree, theme.font_italic,
                             theme.size_small, "muted")
        y -= theme.line_height(theme.size_body)
        if detail:
            for line in self.wrap(detail, theme.font, theme.size_small,
                                  theme.right_w - 18 * mm):
                self._text(theme.right_x + 18 * mm, y, line, theme.font,
                           theme.size_small, "muted")
                y -= theme.line_height(theme.size_small)
        self.y_right = y - 1.0 * mm

    def note_line(self, text):
        """Single bulleted line in the right column (certifications, notes)."""
        theme = self.theme
        y = self.y_right
        self._text(theme.right_x, y, BULLET, theme.font_bold, theme.size_body, "accent")
        for line in self.wrap(text, theme.font, theme.size_body, theme.right_w - 3.5 * mm):
            self._text(theme.right_x + 3.2 * mm, y, line, theme.font, theme.size_body, "text")
            y -= theme.line_height(theme.size_body)
        self.y_right = y - 0.6 * mm

    def links_line(self, links):
        theme = self.theme
        x, y = theme.right_x, self.y_right
        for index, (label, url) in enumerate(links):
            if index:
                self._text(x, y, "|", theme.font, theme.size_small, "divider")
                x += 3 * mm
            x += self.link(x, y, label, url) + 3 * mm
        self.y_right = y - 4.5 * mm

    # ---- left column ---------------------------------------------
    def section_left(self, label):
        theme = self.theme
        y = self.y_left
        self._text(theme.ml, y, label.upper(), theme.font_bold,
                   theme.size_section - 0.5, "accent")
        width = self.c.stringWidth(label.upper(), theme.font_bold, theme.size_section - 0.5)
        self.c.setStrokeColor(theme.color("accent"))
        self.c.setLineWidth(0.7)
        self.c.line(theme.ml + width + 3, y + 2.5, theme.left_w - 6 * mm, y + 2.5)
        self.y_left = y - 5.5 * mm

    def photo(self, path, diameter=30):
        """Circular portrait, centred in the sidebar. Optional by design."""
        theme = self.theme
        size = diameter * mm
        x = (theme.left_w - size) / 2
        y = self.y_left - size + 4 * mm
        self.c.saveState()
        clip = self.c.beginPath()
        clip.circle(x + size / 2, y + size / 2, size / 2)
        self.c.clipPath(clip, stroke=0)
        self.c.drawImage(path, x, y, size, size, preserveAspectRatio=True,
                         anchor="c", mask="auto")
        self.c.restoreState()
        self.c.setStrokeColor(theme.color("accent"))
        self.c.setLineWidth(1.2)
        self.c.circle(x + size / 2, y + size / 2, size / 2, stroke=1, fill=0)
        self.y_left = y - 5 * mm

    def contact_line(self, text, url=None, bold=False):
        theme = self.theme
        y = self.y_left
        font = theme.font_bold if bold else theme.font
        for line in self.wrap(text, font, theme.size_small, theme.sidebar_content_w):
            if url:
                self.link(theme.ml, y, line, url, theme.size_small)
            else:
                self._text(theme.ml, y, line, font, theme.size_small, "text")
            y -= theme.line_height(theme.size_small)
        self.y_left = y

    def badge(self, text, kind="green"):
        theme = self.theme
        size = 6.6
        lines = self.wrap(text, theme.font_bold, size, theme.sidebar_content_w - 4 * mm)
        height = 3.2 * mm * len(lines) + 2.4 * mm
        y = self.y_left - height + 3.4 * mm
        self.c.setFillColor(theme.color(kind))
        self.c.roundRect(theme.ml, y, theme.sidebar_content_w, height, 1.4 * mm,
                         fill=1, stroke=0)
        text_y = y + height - 3.4 * mm
        for line in lines:
            self._text(theme.ml + 2 * mm, text_y, line, theme.font_bold, size, WHITE)
            text_y -= 3.2 * mm
        self.y_left = y - 3.0 * mm

    def language(self, name, level=None, ratio=None, note=None):
        theme = self.theme
        y = self.y_left
        self._text(theme.ml, y, name, theme.font_bold, theme.size_small, "text")
        if level:
            self._text_right(theme.ml + theme.sidebar_content_w, y, level,
                             theme.font, theme.size_small - 0.4, "muted")
        y -= 2.6 * mm
        if ratio is not None:
            width = theme.sidebar_content_w
            self.c.setFillColor(theme.color("divider"))
            self.c.roundRect(theme.ml, y - 0.4 * mm, width, 1.5 * mm, 0.7 * mm,
                             fill=1, stroke=0)
            self.c.setFillColor(theme.color("accent"))
            self.c.roundRect(theme.ml, y - 0.4 * mm, width * max(0.0, min(1.0, ratio)),
                             1.5 * mm, 0.7 * mm, fill=1, stroke=0)
            y -= 3.4 * mm
        if note:
            for line in self.wrap(note, theme.font, theme.size_small - 0.8,
                                  theme.sidebar_content_w):
                self._text(theme.ml, y, line, theme.font, theme.size_small - 0.8, "muted")
                y -= theme.line_height(theme.size_small - 0.8)
        self.y_left = y - 1.4 * mm

    def project(self, name, period=None, description=None, stack=None, links=()):
        theme = self.theme
        y = self.y_left
        self._text(theme.ml, y, name, theme.font_bold, theme.size_small + 0.4, "dark")
        y -= 3.4 * mm
        if period:
            self._text(theme.ml, y, period, theme.font_italic, theme.size_small - 1, "muted")
            y -= 3.2 * mm
        for line in self.wrap(description or "", theme.font, theme.size_small - 0.6,
                              theme.sidebar_content_w):
            self._text(theme.ml, y, line, theme.font, theme.size_small - 0.6, "text")
            y -= theme.line_height(theme.size_small - 0.6)
        if stack:
            for line in self.wrap(stack, theme.font_italic, theme.size_small - 1,
                                  theme.sidebar_content_w):
                self._text(theme.ml, y, line, theme.font_italic,
                           theme.size_small - 1, "muted")
                y -= theme.line_height(theme.size_small - 1)
        for label, url in links:
            self.link(theme.ml, y, label, url, theme.size_small - 0.6)
            y -= 3.2 * mm
        self.y_left = y - 1.6 * mm

    def sidebar_item(self, text, bullet=True):
        theme = self.theme
        y = self.y_left
        indent = 3.0 * mm if bullet else 0
        lines = self.wrap(text, theme.font, theme.size_small,
                          theme.sidebar_content_w - indent)
        for index, line in enumerate(lines):
            if bullet and index == 0:
                self._text(theme.ml, y, BULLET, theme.font_bold, theme.size_small, "accent")
            self._text(theme.ml + indent, y, line, theme.font, theme.size_small, "text")
            y -= theme.line_height(theme.size_small)
        self.y_left = y

    def sidebar_education(self, years, school, degree=None):
        theme = self.theme
        y = self.y_left
        self._text(theme.ml, y, years, theme.font_bold, theme.size_small - 0.6, "accent")
        y -= 3.2 * mm
        for line in self.wrap(school, theme.font_bold, theme.size_small - 0.4,
                              theme.sidebar_content_w):
            self._text(theme.ml, y, line, theme.font_bold, theme.size_small - 0.4, "dark")
            y -= theme.line_height(theme.size_small - 0.4)
        if degree:
            for line in self.wrap(degree, theme.font_italic, theme.size_small - 1,
                                  theme.sidebar_content_w):
                self._text(theme.ml, y, line, theme.font_italic,
                           theme.size_small - 1, "muted")
                y -= 3.0 * mm
        self.y_left = y - 1.4 * mm

    def spacer(self, column, amount_mm):
        if column == "left":
            self.y_left -= amount_mm * mm
        else:
            self.y_right -= amount_mm * mm
