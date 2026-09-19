"""Turn a rich Markdown document into a clean PDF.

    python tools/md_to_pdf_rich.py notes.md [output.pdf]

Useful for everything around the CV that is not the CV: interview notes, a
company brief, a comparison table, a recruiter one-pager. Supports headings
(# to ####), **bold**, *italic*, `code`, [links](url), bullet and numbered
lists, checkboxes, tables, blockquotes, fenced code blocks and --- rules.

    --footer "Your Name"    prints a name at the bottom of every page
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, Preformatted
)

from cvkit.theme import Theme

# Same palette as the CV, so a document and a CV look like one set.
_THEME    = Theme()
DARK      = _THEME.color("dark")
ACCENT    = _THEME.color("accent")
LIGHT_BG  = _THEME.color("sidebar_bg")
MID_GRAY  = _THEME.color("muted")
LINK_BLUE = _THEME.color("link")
BORDER    = _THEME.color("divider")
HEADER_BG = _THEME.color("text")
QUOTE_BG  = colors.HexColor("#FEF2F2")
ROW_ALT   = colors.HexColor("#F9FAFB")

W, H = A4
MARGIN_L = 15*mm
MARGIN_R = 15*mm
MARGIN_TOP = 15*mm
MARGIN_BOT = 15*mm
USABLE_W = W - MARGIN_L - MARGIN_R


# ───────────── Styles ─────────────
base = ParagraphStyle(
    'base', fontName='Helvetica', fontSize=9.5, leading=13, textColor=DARK
)
h1 = ParagraphStyle(
    'h1', parent=base, fontName='Helvetica-Bold', fontSize=18, leading=22,
    textColor=DARK, spaceBefore=6*mm, spaceAfter=3*mm,
)
h2 = ParagraphStyle(
    'h2', parent=base, fontName='Helvetica-Bold', fontSize=13, leading=16,
    textColor=ACCENT, spaceBefore=5*mm, spaceAfter=2*mm,
)
h3 = ParagraphStyle(
    'h3', parent=base, fontName='Helvetica-Bold', fontSize=11, leading=14,
    textColor=DARK, spaceBefore=3.5*mm, spaceAfter=1.5*mm,
)
h4 = ParagraphStyle(
    'h4', parent=base, fontName='Helvetica-Bold', fontSize=10, leading=13,
    textColor=DARK, spaceBefore=2.5*mm, spaceAfter=1*mm,
)
body = ParagraphStyle(
    'body', parent=base, fontSize=9.5, leading=13, spaceAfter=1*mm
)
bullet = ParagraphStyle(
    'bullet', parent=base, fontSize=9.5, leading=13,
    leftIndent=12, bulletIndent=2, spaceAfter=0.5*mm,
)
quote = ParagraphStyle(
    'quote', parent=base, fontSize=9.5, leading=13,
    fontName='Helvetica-Oblique', textColor=colors.HexColor("#374151"),
)
th_style = ParagraphStyle(
    'th', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white
)
td_style = ParagraphStyle(
    'td', fontName='Helvetica', fontSize=7.8, leading=10, textColor=DARK
)
td_first = ParagraphStyle(
    'td_first', fontName='Helvetica-Bold', fontSize=7.8, leading=10, textColor=DARK
)
code_block = ParagraphStyle(
    'code_block', fontName='Courier', fontSize=8, leading=10.5,
    textColor=DARK, leftIndent=0, backColor=LIGHT_BG,
    borderColor=BORDER, borderWidth=0.3, borderPadding=6,
    spaceBefore=2*mm, spaceAfter=2*mm,
)


# ---- inline markdown ----
def _escape_html(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(s):
    s = _escape_html(s)
    # links [text](url)
    s = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<link href="{m.group(2)}" color="#2563EB"><u>{m.group(1)}</u></link>',
        s,
    )
    # bold **x**
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    # italic *x* (after bold, so ** is not broken)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", s)
    # inline code `x`
    s = re.sub(
        r"`([^`]+)`",
        lambda m: f'<font face="Courier" color="#B91C1C">{m.group(1)}</font>',
        s,
    )
    return s


# ---- block helpers ----
def make_table(header, rows):
    n = len(header)
    # column weights depend on how many columns there are
    if n == 2:
        weights = [1, 2]
    elif n == 3:
        weights = [2, 2, 3]
    elif n == 4:
        weights = [2, 2, 1.5, 3]
    else:
        weights = [1] * n
    total = sum(weights)
    col_widths = [USABLE_W * (w/total) for w in weights]

    data = [[Paragraph(inline(c), th_style) for c in header]]
    for r in rows:
        row_cells = []
        for idx, c in enumerate(r):
            style = td_first if idx == 0 else td_style
            row_cells.append(Paragraph(inline(c), style))
        data.append(row_cells)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        # header row
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        # body rows
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.3, BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        # accent bar down the first column
        ('LINEBEFORE', (0, 1), (0, -1), 2, ACCENT),
    ]))
    return t


def make_blockquote(text):
    p = Paragraph(inline(text), quote)
    t = Table([[p]], colWidths=[USABLE_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), QUOTE_BG),
        ('LINEBEFORE', (0, 0), (0, -1), 3, ACCENT),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


# ---- parser ----
TABLE_SEP_RE = re.compile(r"^\|?[\s:|\-]+\|[\s:|\-]*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$")
NUM_RE = re.compile(r"^\s*(\d+)\.\s+(.+)$")
CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+)$")


def _split_table_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse_md(md_text):
    flow = []
    lines = md_text.split("\n")
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].rstrip()

        # blank line
        if not line.strip():
            i += 1
            continue

        # --- rule
        if line.strip() == "---":
            flow.append(HRFlowable(
                width="100%", thickness=0.5, color=BORDER,
                spaceBefore=3*mm, spaceAfter=3*mm,
            ))
            i += 1
            continue

        # fenced code block
        if line.strip().startswith("```"):
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1  # closing fence
            code_text = "\n".join(code_lines)
            flow.append(Preformatted(code_text, code_block))
            continue

        # heading
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            style = {1: h1, 2: h2, 3: h3, 4: h4}.get(level, h4)
            flow.append(Paragraph(inline(text), style))
            i += 1
            continue

        # table: a | row followed by a |---|---| separator
        if line.strip().startswith("|") and i + 1 < n and TABLE_SEP_RE.match(lines[i+1].strip()):
            header = _split_table_row(line)
            i += 2  # header + separator
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_split_table_row(lines[i]))
                i += 1
            flow.append(make_table(header, rows))
            flow.append(Spacer(1, 3*mm))
            continue

        # blockquote
        if line.lstrip().startswith(">"):
            quote_lines = []
            while i < n and lines[i].lstrip().startswith(">"):
                quote_lines.append(lines[i].lstrip().lstrip(">").strip())
                i += 1
            text = " ".join(l for l in quote_lines if l)
            if text:
                flow.append(make_blockquote(text))
                flow.append(Spacer(1, 2*mm))
            continue

        # checkbox list
        if CHECKBOX_RE.match(line):
            while i < n and CHECKBOX_RE.match(lines[i]):
                m = CHECKBOX_RE.match(lines[i])
                mark = "X" if m.group(1).lower() == "x" else " "
                item_text = m.group(2)
                flow.append(Paragraph(
                    f'<font face="Courier">[{mark}]</font> ' + inline(item_text),
                    bullet,
                ))
                i += 1
            flow.append(Spacer(1, 1.5*mm))
            continue

        # bullet list
        if BULLET_RE.match(line):
            while i < n and BULLET_RE.match(lines[i]):
                m = BULLET_RE.match(lines[i])
                flow.append(Paragraph("• " + inline(m.group(1)), bullet))
                i += 1
            flow.append(Spacer(1, 1.5*mm))
            continue

        # numbered list
        if NUM_RE.match(line):
            while i < n and NUM_RE.match(lines[i]):
                m = NUM_RE.match(lines[i])
                flow.append(Paragraph(
                    f"{m.group(1)}. " + inline(m.group(2)), bullet,
                ))
                i += 1
            flow.append(Spacer(1, 1.5*mm))
            continue

        # paragraph: accumulate until a blank line or a block starts
        para_lines = [line]
        i += 1
        while i < n:
            nxt = lines[i].rstrip()
            if not nxt.strip():
                break
            if (HEADING_RE.match(nxt) or nxt.strip() == "---"
                or nxt.strip().startswith("|") or nxt.lstrip().startswith(">")
                or BULLET_RE.match(nxt) or NUM_RE.match(nxt)):
                break
            para_lines.append(nxt)
            i += 1
        text = " ".join(para_lines)
        flow.append(Paragraph(inline(text), body))

    return flow


# ---- page furniture ----
def _page_decor(canvas, doc, footer=""):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MID_GRAY)
    canvas.drawRightString(W - MARGIN_R, 8*mm, f"{doc.page}")
    if footer:
        canvas.drawString(MARGIN_L, 8*mm, footer)
    canvas.restoreState()


def generate(input_path, output_path, footer=""):
    with open(input_path, "r", encoding="utf-8") as f:
        md = f.read()

    flow = parse_md(md)

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOT,
        title=os.path.splitext(os.path.basename(output_path))[0],
    )
    decor = lambda canvas, doc: _page_decor(canvas, doc, footer)
    doc.build(flow, onFirstPage=decor, onLaterPages=decor)
    print(f"Done - {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Markdown to PDF, rich flavour")
    parser.add_argument("input", help="source .md file")
    parser.add_argument("output", nargs="?", help="target .pdf (default: same name)")
    parser.add_argument("--footer", default="", help="text printed at the bottom of each page")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"Error: {args.input} not found")

    generate(args.input, args.output or os.path.splitext(args.input)[0] + ".pdf",
             args.footer)
