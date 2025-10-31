"""Visual, side-by-side PDF helpers.

Two capabilities:
- Render a given page from two PDFs as PNG bytes for side-by-side viewing.
- Merge two PDFs into a single PDF with pages aligned horizontally.

Uses PyMuPDF (fitz) for reliable rendering and composition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Optional

import fitz  # PyMuPDF


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
