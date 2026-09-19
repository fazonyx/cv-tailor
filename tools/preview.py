#!/usr/bin/env python3
"""Regenerate the images used by the README.

    pip install -r requirements-dev.txt
    python build.py && python tools/preview.py

Without this, the pictures in the README are orphan artefacts: the layout
changes, the PDFs change, and the screenshots quietly keep showing an older
version of the project. Anyone can rebuild them from the committed PDFs.
"""
import sys
from pathlib import Path

import fitz                      # PyMuPDF
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "images"

# (pdf, page index, output name)
PAGES = [
    ("applications/orbital-freight/CV_Alex_Morand_Orbital_Freight.pdf", 0,
     "preview-backend.png"),
    ("applications/quayside-systems/CV_Alex_Morand_Quayside.pdf", 0,
     "preview-solutions.png"),
    ("applications/quayside-systems/CV_Alex_Morand_Quayside.pdf", 1,
     "preview-solutions-fr.png"),
    ("applications/orbital-freight/letter.pdf", 0, "preview-letter.png"),
]

DPI = 120
GUTTER = 26
MAX_WIDTH = 1700


def render_pages():
    IMAGES.mkdir(parents=True, exist_ok=True)
    for source, index, name in PAGES:
        path = ROOT / source
        if not path.exists():
            sys.exit(f"{source} is missing - run `python build.py` first")
        with fitz.open(path) as document:
            document[index].get_pixmap(dpi=DPI).save(IMAGES / name)
        print(f"  {name}")


def render_comparison():
    """The two offers side by side - the picture the README opens with."""
    left = Image.open(IMAGES / "preview-backend.png")
    right = Image.open(IMAGES / "preview-solutions.png")
    canvas = Image.new("RGB", (left.width + GUTTER + right.width, left.height), "white")
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + GUTTER, 0))
    middle = left.width + GUTTER // 2
    ImageDraw.Draw(canvas).line([(middle, 0), (middle, left.height)],
                                fill="#D1D5DB", width=2)
    canvas.thumbnail((MAX_WIDTH, MAX_WIDTH))
    canvas.save(IMAGES / "two-offers.png")
    print("  two-offers.png")


if __name__ == "__main__":
    print("Rendering previews into docs/images:")
    render_pages()
    render_comparison()
