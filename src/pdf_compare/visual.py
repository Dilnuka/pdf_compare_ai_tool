"""Visual, side-by-side PDF helpers.

Two capabilities:
- Render a given page from two PDFs as PNG bytes for side-by-side viewing.
- Merge two PDFs into a single PDF with pages aligned horizontally.

Uses PyMuPDF (fitz) for reliable rendering and composition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import re

import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import difflib
import imagehash


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


def text_diff_stats(
    pdf_a: bytes | str | Path,
    pdf_b: bytes | str | Path,
    page_index: int,
) -> Dict[str, Any]:
    """Compute detailed statistics about text differences on a page.
    
    Returns a dict with:
        - text_changes: number of non-numeric word changes
        - number_changes: number of numeric word changes
        - total_word_changes: total word-level changes
        - image_changes: number of image differences (using perceptual hash)
    """
    def _get_doc(src):
        if isinstance(src, fitz.Document):
            return src, False
        if isinstance(src, (bytes, bytearray)):
            return fitz.open(stream=src, filetype="pdf"), True
        return fitz.open(str(src)), True
    
    def _is_number(word: str) -> bool:
        # Match numbers with optional commas, dots, currency symbols, percentages
        return bool(re.match(r'^[\$€£¥]?[\d,]+\.?\d*%?$', word.strip()))
    
    def _extract_image_hashes(page: fitz.Page, doc: fitz.Document) -> List[str]:
        """Extract perceptual hashes for all images on a page."""
        hashes = []
        image_list = page.get_images(full=False)
        for img_index, img_info in enumerate(image_list):
            try:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                if base_image:
                    img_bytes = base_image["image"]
                    pil_img = Image.open(io.BytesIO(img_bytes))
                    # Use perceptual hash
                    phash = str(imagehash.phash(pil_img))
                    hashes.append(phash)
            except Exception:
                # If extraction fails, use a placeholder
                hashes.append(f"error_{img_index}")
        return hashes
    
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
        
        text_count = 0
        number_count = 0
        
        for tag, a0, a1, b0, b1 in sm.get_opcodes():
            if tag in ("replace", "delete"):
                for i in range(a0, a1):
                    if _is_number(tok_a[i]):
                        number_count += 1
                    else:
                        text_count += 1
            if tag in ("replace", "insert"):
                for i in range(b0, b1):
                    if _is_number(tok_b[i]):
                        number_count += 1
                    else:
                        text_count += 1
        
        # Compare images using perceptual hashing
        hashes_a = _extract_image_hashes(pa, da)
        hashes_b = _extract_image_hashes(pb, db)
        
        # Count images that are different
        # Match by position first, then check hash
        max_images = max(len(hashes_a), len(hashes_b))
        image_changes = 0
        
        for i in range(max_images):
            hash_a = hashes_a[i] if i < len(hashes_a) else None
            hash_b = hashes_b[i] if i < len(hashes_b) else None
            
            if hash_a is None or hash_b is None:
                # Image added or removed
                image_changes += 1
            elif hash_a != hash_b:
                # Image replaced/modified
                image_changes += 1
        
        return {
            "text_changes": text_count,
            "number_changes": number_count,
            "image_changes": image_changes,
            "total_word_changes": text_count + number_count,
        }
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
    opacity: float = 0.18,  # 0..1
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
                # Use outline only instead of filled rectangle for readability
                draw.rectangle(rr, outline=(255, 215, 0, 255), width=2)
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
    add_legend: bool = True,
) -> bytes:
    """Merge PDFs side-by-side and overlay rectangle outlines on text diffs.

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
        
        legend_height = 30 if add_legend else 0
        
        for i in range(n):
            pa = da[i]
            pb = db[i]
            wa, ha = pa.rect.width, pa.rect.height
            wb, hb = pb.rect.width, pb.rect.height
            W, H = wa + wb, max(ha, hb) + legend_height
            new_page = out.new_page(width=W, height=H)
            
            # Add legend banner at top if enabled
            if add_legend:
                shape = new_page.new_shape()
                # Background bar
                shape.draw_rect(fitz.Rect(0, 0, W, legend_height))
                shape.finish(color=(0.95, 0.95, 0.95), fill=(0.95, 0.95, 0.95))
                shape.commit()
                
                # Legend text
                legend_text = "Yellow highlights indicate text/number differences | PDF A (Left) vs PDF B (Right)"
                new_page.insert_text(
                    (10, 18),
                    legend_text,
                    fontsize=10,
                    color=(0.2, 0.2, 0.2),
                    fontname="helv"
                )
                
                # Small yellow sample box (filled to match the highlights)
                sample_shape = new_page.new_shape()
                sample_rect = fitz.Rect(W - 120, 8, W - 105, 22)
                sample_shape.draw_rect(sample_rect)
                sample_shape.finish(color=None, fill=fill_color, fill_opacity=0.3)
                sample_shape.commit()
            
            # Show PDF pages (shifted down if legend is present)
            new_page.show_pdf_page(fitz.Rect(0, legend_height, wa, legend_height + ha), da, i)
            new_page.show_pdf_page(fitz.Rect(wa, legend_height, wa + wb, legend_height + hb), db, i)

            # Compute diff rects on original pages
            tok_rects_a, tok_rects_b = text_diff_rects(pdf_a=da, pdf_b=db, page_index=i)
            
            # Use filled highlights with opacity for PDF export
            def _add_annots(rects: List[fitz.Rect], x_shift: float = 0.0, y_shift: float = 0.0):
                for r in rects:
                    rect = fitz.Rect(r.x0 + x_shift, r.y0 + y_shift, r.x1 + x_shift, r.y1 + y_shift)
                    # Draw filled rectangle with light opacity
                    shape = new_page.new_shape()
                    shape.draw_rect(rect)
                    shape.finish(color=None, fill=fill_color, fill_opacity=0.3)
                    shape.commit()

            _add_annots(tok_rects_a, 0.0, legend_height)
            _add_annots(tok_rects_b, wa, legend_height)

        data = out.tobytes()
        if out_path:
            Path(out_path).write_bytes(data)
        return data
