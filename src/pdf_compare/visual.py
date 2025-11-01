"""Visual, side-by-side PDF helpers.

Two capabilities:
- Render a given page from two PDFs as PNG bytes for side-by-side viewing.
- Merge two PDFs into a single PDF with pages aligned horizontally.

Uses PyMuPDF (fitz) for reliable rendering and composition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Optional, List

import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import difflib


def render_page_pair_png(
    pdf_a: bytes | str | Path,
    pdf_b: bytes | str | Path,
    page_index: int,
    zoom: float = 2.0,
) -> Tuple[bytes, bytes]:
    """Render the same page index from two PDFs to PNG bytes.

    Args:
        pdf_a: Bytes, path string, or Path to first PDF.
        pdf_b: Bytes, path string, or Path to second PDF.
        page_index: Zero-based page index to render.
        zoom: Scale factor (1.0 = 72dpi). 2.0 ~ 144dpi.

    Returns:
        Tuple of (png_bytes_a, png_bytes_b)
    """
    def _open(src):
        if isinstance(src, (bytes, bytearray)):
            return fitz.open(stream=src, filetype="pdf")
        return fitz.open(str(src))

    mat = fitz.Matrix(zoom, zoom)
    with _open(pdf_a) as da, _open(pdf_b) as db:
        if page_index < 0:
            raise IndexError("page_index must be >= 0")
        if page_index >= min(len(da), len(db)):
            raise IndexError("page_index out of range for one of the PDFs")
        pa = da[page_index]
        pb = db[page_index]
        pixa = pa.get_pixmap(matrix=mat, alpha=False)
        pixb = pb.get_pixmap(matrix=mat, alpha=False)
        return pixa.tobytes("png"), pixb.tobytes("png")


def merge_side_by_side(
    pdf_a: bytes | str | Path,
    pdf_b: bytes | str | Path,
    out_path: Optional[str | Path] = None,
    max_pages: Optional[int] = None,
) -> bytes:
    """Merge two PDFs horizontally page-by-page.

    Creates a new PDF where each output page places PDF A on the left and
    PDF B on the right. Width is wA + wB, height is max(hA, hB) per pair.

    Args:
        pdf_a, pdf_b: Bytes or path to input PDFs.
        out_path: Optional path to write the merged PDF.
        max_pages: If provided, limit the number of merged page pairs.

    Returns:
        Bytes of the merged PDF.
    """
    def _open(src):
        if isinstance(src, (bytes, bytearray)):
            return fitz.open(stream=src, filetype="pdf")
        return fitz.open(str(src))

    with _open(pdf_a) as da, _open(pdf_b) as db:
        n = min(len(da), len(db))
        if max_pages is not None:
            n = min(n, max_pages)
        out = fitz.open()
        for i in range(n):
            pa = da[i]
            pb = db[i]
            wa, ha = pa.rect.width, pa.rect.height
            wb, hb = pb.rect.width, pb.rect.height
            W, H = wa + wb, max(ha, hb)
            new_page = out.new_page(width=W, height=H)
            # Left: A at (0, 0, wa, ha)
            new_page.show_pdf_page(fitz.Rect(0, 0, wa, ha), da, i)
            # Right: B shifted by wa
            new_page.show_pdf_page(fitz.Rect(wa, 0, wa + wb, hb), db, i)
        data = out.tobytes()
        if out_path:
            Path(out_path).write_bytes(data)
        return data


# ---- Text diff highlighting helpers ----

def _page_word_tokens_and_rects(page: fitz.Page) -> Tuple[List[str], List[fitz.Rect]]:
    words = page.get_text("words")  # [x0, y0, x1, y1, word, block, line, word_no]
    tokens = [w[4] for w in words]
    rects = [fitz.Rect(w[:4]) for w in words]
    return tokens, rects


def text_diff_rects(
    pdf_a: bytes | str | Path,
    pdf_b: bytes | str | Path,
    page_index: int,
) -> Tuple[List[fitz.Rect], List[fitz.Rect]]:
    """Compute rectangles of differing words for a given page pair.

    Returns two lists of rectangles: (rects_in_A, rects_in_B) that represent
    tokens involved in replace/insert/delete operations.
    """
    def _get_doc(src):
        if isinstance(src, fitz.Document):
            return src, False
        if isinstance(src, (bytes, bytearray)):
            return fitz.open(stream=src, filetype="pdf"), True
        return fitz.open(str(src)), True

    da, close_a = _get_doc(pdf_a)
    db, close_b = _get_doc(pdf_b)
    try:
        if page_index < 0 or page_index >= min(len(da), len(db)):
            raise IndexError("page_index out of range for one of the PDFs")
        pa = da[page_index]
        pb = db[page_index]
        tok_a, rect_a = _page_word_tokens_and_rects(pa)
        tok_b, rect_b = _page_word_tokens_and_rects(pb)
        sm = difflib.SequenceMatcher(None, tok_a, tok_b)
        diff_rects_a: List[fitz.Rect] = []
        diff_rects_b: List[fitz.Rect] = []
        for tag, a0, a1, b0, b1 in sm.get_opcodes():
            if tag in ("replace", "delete"):
                diff_rects_a.extend(rect_a[a0:a1])
            if tag in ("replace", "insert"):
                diff_rects_b.extend(rect_b[b0:b1])
        return diff_rects_a, diff_rects_b
    finally:
        if close_a:
            da.close()
        if close_b:
            db.close()


def render_page_pair_png_highlight(
    pdf_a: bytes | str | Path,
    pdf_b: bytes | str | Path,
    page_index: int,
    zoom: float = 2.0,
    color: Tuple[int, int, int, int] = (255, 215, 0, 96),  # translucent gold
) -> Tuple[bytes, bytes]:
    """Render page pair with rectangles highlighting differing words.

    Returns two PNG byte blobs with overlays drawn.
    """
    rects_a, rects_b = text_diff_rects(pdf_a, pdf_b, page_index)

    def _open(src):
        if isinstance(src, (bytes, bytearray)):
            return fitz.open(stream=src, filetype="pdf")
        return fitz.open(str(src))

    mat = fitz.Matrix(zoom, zoom)
    with _open(pdf_a) as da, _open(pdf_b) as db:
        pa = da[page_index]
        pb = db[page_index]
        pixa = pa.get_pixmap(matrix=mat, alpha=False)
        pixb = pb.get_pixmap(matrix=mat, alpha=False)

        def _overlay(pix: fitz.Pixmap, rects: List[fitz.Rect]) -> bytes:
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img = img.convert("RGBA")
            draw = ImageDraw.Draw(img, "RGBA")
            for r in rects:
                rr = [r.x0 * zoom, r.y0 * zoom, r.x1 * zoom, r.y1 * zoom]
                draw.rectangle(rr, fill=color)
            with io.BytesIO() as buf:
                img.save(buf, format="PNG")
                return buf.getvalue()

        return _overlay(pixa, rects_a), _overlay(pixb, rects_b)


def merge_side_by_side_with_text_highlight(
    pdf_a: bytes | str | Path,
    pdf_b: bytes | str | Path,
    out_path: Optional[str | Path] = None,
    max_pages: Optional[int] = None,
    fill_color: Tuple[float, float, float] = (1.0, 0.84, 0.0),  # gold
    fill_opacity: float = 0.25,
) -> bytes:
    """Merge PDFs side-by-side and overlay translucent rectangles on text diffs.

    Returns the merged PDF bytes (and writes to out_path if provided).
    """
    def _open(src):
        if isinstance(src, (bytes, bytearray)):
            return fitz.open(stream=src, filetype="pdf")
        return fitz.open(str(src))

    with _open(pdf_a) as da, _open(pdf_b) as db:
        n = min(len(da), len(db))
        if max_pages is not None:
            n = min(n, max_pages)
        out = fitz.open()
        for i in range(n):
            pa = da[i]
            pb = db[i]
            wa, ha = pa.rect.width, pa.rect.height
            wb, hb = pb.rect.width, pb.rect.height
            W, H = wa + wb, max(ha, hb)
            new_page = out.new_page(width=W, height=H)
            new_page.show_pdf_page(fitz.Rect(0, 0, wa, ha), da, i)
            new_page.show_pdf_page(fitz.Rect(wa, 0, wa + wb, hb), db, i)

            # Compute diff rects on original pages
            tok_rects_a, tok_rects_b = text_diff_rects(pdf_a=da, pdf_b=db, page_index=i)
            # Draw translucent rectangles
            shape = new_page.new_shape()
            for r in tok_rects_a:
                shape.draw_rect(r)
            for r in tok_rects_b:
                shape.draw_rect(fitz.Rect(r.x0 + wa, r.y0, r.x1 + wa, r.y1))
            shape.finish(color=None, fill=fill_color, fill_opacity=fill_opacity, stroke_opacity=0)
            shape.commit()

        data = out.tobytes()
        if out_path:
            Path(out_path).write_bytes(data)
        return data
