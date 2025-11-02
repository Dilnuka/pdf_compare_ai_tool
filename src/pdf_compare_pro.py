"""
Pro mode (Side‑by‑Side):
- Merge two PDFs page-by-page horizontally (A left, B right)
- Optional text-difference highlights (word-level) on the merged PDF

This replaces the previous semantic pipeline.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import sys
ROOT = Path(__file__).resolve().parents[1]  # project root
src_path = ROOT  # this file lives in src/, so current dir is already src when executed as script
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from pdf_compare.visual import (  # type: ignore
    merge_side_by_side,
    merge_side_by_side_with_text_highlight,
)


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def merge_pro(
    pdf_a: str,
    pdf_b: str,
    out: Optional[str] = None,
    highlight: bool = False,
    max_pages: Optional[int] = None,
) -> str:
    """Create a side-by-side merged PDF.

    Args:
        pdf_a, pdf_b: input PDF paths
        out: output PDF path; defaults based on highlight flag
        highlight: overlay word-level text-diff rectangles
        max_pages: limit number of merged page pairs

    Returns: output file path
    """
    out_path = out or ("side_by_side_highlighted.pdf" if highlight else "side_by_side.pdf")
    if highlight:
        data = merge_side_by_side_with_text_highlight(pdf_a, pdf_b, out_path=out_path, max_pages=max_pages)
    else:
        data = merge_side_by_side(pdf_a, pdf_b, out_path=out_path, max_pages=max_pages)
    # If caller passed no out path and wants the bytes, we already wrote file; still return path
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Pro (Side‑by‑Side) PDF merge tool")
    parser.add_argument("pdf_a", help="Left PDF")
    parser.add_argument("pdf_b", help="Right PDF")
    parser.add_argument("--out", help="Output PDF path")
    parser.add_argument("--highlight", action="store_true", help="Highlight text differences")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit number of page pairs")
    args = parser.parse_args()

    out_file = merge_pro(args.pdf_a, args.pdf_b, out=args.out, highlight=args.highlight, max_pages=args.max_pages)
    logger.info("Merged PDF written to %s", out_file)


if __name__ == "__main__":
    main()
