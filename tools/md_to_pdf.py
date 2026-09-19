"""Turn a cover letter written in Markdown into a laid-out PDF.

    python tools/md_to_pdf.py applications/<company>/letter.md [output.pdf]

The letter keeps the palette of the CV, so both documents look like one
application. Structure expected (all parts optional):

    Name
    city, country
    name@example.com
    https://www.linkedin.com/in/example

    Subject: ...            (or "Objet :" in French)

    Dear ...,

    ...paragraphs...

    Sincerely,
    Name

A line containing only `---` starts a new page: that is how a bilingual
letter (English page, French page) is written in a single file.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from cvkit.theme import Theme

W, H = A4
MARGIN_L = 25*mm
MARGIN_R = 25*mm
MARGIN_TOP = 25*mm
MARGIN_BOT = 25*mm
USABLE_W = W - MARGIN_L - MARGIN_R

_THEME = Theme()
DARK = _THEME.color("text")
ACCENT = _THEME.color("accent")
MID_GRAY = _THEME.color("muted")
LINK_BLUE = _THEME.color("link")

# Closings that mark the signature block, in the languages the template ships
# with. Add your own rather than hard-coding a name anywhere in this file.
CLOSINGS = ("Sincerely", "Kind regards", "Best regards", "Yours sincerely",
            "Cordialement", "Bien cordialement", "Respectueusement")
PHONE = re.compile(r"^[+(]?\d[\d\s().-]{6,}$")

def wrap_text(c, text, font, size, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if c.stringWidth(test, font, size) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]

def draw_lines(c, lines, y, font, size, color, line_height, max_w):
    c.setFont(font, size)
    c.setFillColor(color)
    for line in lines:
        if y < MARGIN_BOT:
            c.showPage()
            y = H - MARGIN_TOP
            c.setFont(font, size)
            c.setFillColor(color)
        c.drawString(MARGIN_L, y, line)
        y -= line_height
    return y

def parse_page(page_content):
    blocks = []
    current_para = []

    for line in page_content.split("\n"):
        stripped = line.strip()
        if stripped == "":
            if current_para:
                blocks.append(("paragraph", " ".join(current_para)))
                current_para = []
            continue

        # A bare URL, or a labelled one, becomes a clickable line
        if stripped.startswith("LinkedIn:") or stripped.startswith("https://"):
            if current_para:
                blocks.append(("paragraph", " ".join(current_para)))
                current_para = []
            url = stripped.replace("LinkedIn: ", "").replace("LinkedIn:", "").strip()
            blocks.append(("link", url))
            continue

        # Subject line
        if stripped.lower().startswith("subject:") or stripped.lower().startswith("objet :") or stripped.lower().startswith("objet:"):
            if current_para:
                blocks.append(("paragraph", " ".join(current_para)))
                current_para = []
            blocks.append(("subject", stripped))
            continue

        # Name: first non-empty line, short, no trailing comma
        if not blocks and len(stripped.split()) <= 4 and not stripped.endswith(","):
            blocks.append(("name", stripped))
            continue

        # Contact details: the short lines that follow the name, before the
        # first real sentence. Address, email, phone, city - all optional.
        header_only = blocks and all(b[0] in ("name", "contact", "link") for b in blocks)
        if header_only and (("@" in stripped) or PHONE.match(stripped)
                            or (len(stripped) <= 60
                                and not stripped.endswith((",", ".", ":", "!", "?")))):
            blocks.append(("contact", stripped))
            continue

        current_para.append(stripped)

    if current_para:
        blocks.append(("paragraph", " ".join(current_para)))

    return blocks


def parse_md(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split on horizontal rule (---) → one page per section
    pages_raw = content.split("\n---\n")
    return [parse_page(p) for p in pages_raw]

def generate(input_path, output_path):
    pages = parse_md(input_path)
    title = os.path.splitext(os.path.basename(output_path))[0]

    c = canvas.Canvas(output_path, pagesize=A4)
    c.setTitle(title)

    for page_idx, blocks in enumerate(pages):
        if page_idx > 0:
            c.showPage()
        y = H - MARGIN_TOP
        past_header = False

        for btype, content in blocks:
            if btype == "name":
                c.setFont("Helvetica-Bold", 12)
                c.setFillColor(DARK)
                c.drawString(MARGIN_L, y, content)
                y -= 6*mm

            elif btype == "contact":
                c.setFont("Helvetica", 9)
                c.setFillColor(MID_GRAY)
                c.drawString(MARGIN_L, y, content)
                y -= 4*mm

            elif btype == "link":
                c.setFillColor(LINK_BLUE)
                c.setFont("Helvetica", 9)
                display = content.replace("https://www.", "").replace("https://", "").rstrip("/")
                c.drawString(MARGIN_L, y, display)
                tw = c.stringWidth(display, "Helvetica", 9)
                c.linkURL(content, (MARGIN_L, y - 1, MARGIN_L + tw, y + 8), relative=0)
                y -= 4*mm

            elif btype == "subject":
                if not past_header:
                    y -= 4*mm
                    c.setStrokeColor(ACCENT)
                    c.setLineWidth(1.5)
                    c.line(MARGIN_L, y, W - MARGIN_R, y)
                    y -= 8*mm
                    past_header = True
                c.setFont("Helvetica-Bold", 10)
                c.setFillColor(DARK)
                lines = wrap_text(c, content, "Helvetica-Bold", 10, USABLE_W)
                for line in lines:
                    c.drawString(MARGIN_L, y, line)
                    y -= 4.5*mm
                y -= 6*mm

            elif btype == "paragraph":
                if not past_header:
                    y -= 4*mm
                    c.setStrokeColor(ACCENT)
                    c.setLineWidth(1.5)
                    c.line(MARGIN_L, y, W - MARGIN_R, y)
                    y -= 8*mm
                    past_header = True

                # Signature block
                closing = next((c for c in CLOSINGS if content.strip().startswith(c)), None)
                if closing:
                    y -= 2*mm
                    c.setFont("Helvetica", 10)
                    c.setFillColor(DARK)
                    c.drawString(MARGIN_L, y, closing + ",")
                    y -= 8*mm
                    # Whatever follows the closing is the signature
                    remaining = content.replace(closing + ",", "").strip()
                    if remaining:
                        c.setFont("Helvetica-Bold", 10)
                        c.drawString(MARGIN_L, y, remaining)
                        y -= 6*mm
                    continue

                lines = wrap_text(c, content, "Helvetica", 10, USABLE_W)
                y = draw_lines(c, lines, y, "Helvetica", 10, DARK, 4.5*mm, USABLE_W)

                # Extra air after a salutation or a very short paragraph
                if content.strip().endswith(",") and len(content) < 30:
                    y -= 4*mm
                else:
                    y -= 4*mm

    c.save()
    print(f"Done - {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/md_to_pdf.py letter.md [output.pdf]")
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found")
        sys.exit(1)

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        output_path = os.path.splitext(input_path)[0] + ".pdf"

    generate(input_path, output_path)
