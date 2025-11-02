"""
Copilot: Implement PDF extraction utilities:
- function extract_text_pages(pdf_path) -> list of (page_number, text)
- function extract_tables(pdf_path) -> list of (page_number, dataframe)
- function extract_images(pdf_path) -> list of objects with (page, name, bytes)
- include small helper to save or return image bytes and a thumbnail base64
- ensure safe error handling
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class ExtractedImage:
    page: int
    name: str
    bytes: bytes
    width: int | None = None
    height: int | None = None
    thumbnail_b64: str | None = None


def _make_thumbnail_b64(img_bytes: bytes, max_size: int = 256) -> str:
    """Create a small thumbnail and return base64 string."""
    try:
        with Image.open(io.BytesIO(img_bytes)) as im:
            im = im.convert("RGB")
            im.thumbnail((max_size, max_size))
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        logger.warning("thumbnail generation failed: %s", e)
        return ""


def extract_text_pages(pdf_path: str) -> List[Tuple[int, str]]:
    """Extract text per page using PyMuPDF.

    Returns list of (page_number starting at 1, text)
    """
    results: List[Tuple[int, str]] = []
    try:
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text") or ""
                results.append((i, text))
    except Exception as e:
        logger.error("Failed to extract text from %s: %s", pdf_path, e)
    return results


def extract_tables(pdf_path: str) -> List[Tuple[int, pd.DataFrame]]:
    """Extract tables per page using pdfplumber into DataFrames.

    Returns list of (page_number starting at 1, dataframe)
    """
    tables: List[Tuple[int, pd.DataFrame]] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                page_tables = page.extract_tables() or []
                for tbl in page_tables:
                    try:
                        df = pd.DataFrame(tbl)
                        tables.append((i, df))
                    except Exception as e:
                        logger.debug("Skipping malformed table on page %s: %s", i, e)
    except Exception as e:
        logger.error("Failed to extract tables from %s: %s", pdf_path, e)
    return tables


def extract_images(pdf_path: str) -> List[ExtractedImage]:
    """Extract images using PyMuPDF, returning bytes and basic metadata."""
    images: List[ExtractedImage] = []
    try:
        with fitz.open(pdf_path) as doc:
            for page_index in range(len(doc)):
                page = doc[page_index]
                for img_index, img in enumerate(page.get_images(full=True)):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    img_bytes = base_image.get("image", b"")
                    width = base_image.get("width")
                    height = base_image.get("height")
                    name = f"p{page_index+1}_img{img_index+1}.png"
                    thumb = _make_thumbnail_b64(img_bytes)
                    images.append(
                        ExtractedImage(
                            page=page_index + 1,
                            name=name,
                            bytes=img_bytes,
                            width=width,
                            height=height,
                            thumbnail_b64=thumb,
                        )
                    )
    except Exception as e:
        logger.error("Failed to extract images from %s: %s", pdf_path, e)
    return images
