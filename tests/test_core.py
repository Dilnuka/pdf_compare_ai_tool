"""
Copilot: Create simple pytest tests for core functions:
- test_extract_text_pages loads two sample PDFs in assets/ and asserts that text extraction returns pages > 0
- test_compare_texts verifies difflib output on small strings
- test_image_hash computes phash for two identical images and asserts hamming distance 0
- keep tests lightweight and runnable locally
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure src/ is on path
ROOT = Path(__file__).resolve().parents[1]
src_path = ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from utils.extractor import extract_text_pages  # type: ignore
from utils.compare_text import compare_texts  # type: ignore

import fitz  # PyMuPDF
from PIL import Image
import imagehash
import io

ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)


def _make_pdf(path: Path, text: str):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def test_extract_text_pages(tmp_path):
    a = ASSETS / "sample_P001.pdf"
    b = ASSETS / "sample_P002.pdf"
    if not a.exists():
        _make_pdf(a, "Hello A\nThis is sample PDF A.")
    if not b.exists():
        _make_pdf(b, "Hello B\nThis is sample PDF B.")

    pages_a = extract_text_pages(str(a))
    pages_b = extract_text_pages(str(b))

    assert len(pages_a) > 0
    assert len(pages_b) > 0


def test_compare_texts():
    texts_a = [(1, "alpha\nbeta\n")]
    texts_b = [(1, "alpha\ngamma\n")]
    diffs = compare_texts(texts_a, texts_b)
    assert diffs and "-beta" in diffs[0]["diff_snippet"] and "+gamma" in diffs[0]["diff_snippet"]


def test_image_hash_identical():
    # Create identical images in memory
    img = Image.new("RGB", (64, 64), color=(255, 0, 0))
    buf1, buf2 = io.BytesIO(), io.BytesIO()
    img.save(buf1, format="PNG")
    img.save(buf2, format="PNG")
    buf1.seek(0)
    buf2.seek(0)

    h1 = imagehash.phash(Image.open(buf1))
    h2 = imagehash.phash(Image.open(buf2))
    assert (h1 - h2) == 0
