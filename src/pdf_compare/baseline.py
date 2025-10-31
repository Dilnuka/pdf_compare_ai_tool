"""
pdf_compare.baseline

Baseline PDF comparison pipeline.
"""
from __future__ import annotations

import argparse
import logging
from typing import Dict, Any

from utils.extractor import extract_text_pages, extract_tables, extract_images
from utils.compare_text import compare_texts
from utils.compare_table import compare_tables
from utils.compare_image import compare_images
from utils.report import render_html_report

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def compare_pdfs(pdf_a: str, pdf_b: str) -> Dict[str, Any]:
    """Run baseline comparison across text, tables, images."""
    logger.info("Extracting from A: %s", pdf_a)
    texts_a = extract_text_pages(pdf_a)
    tables_a = extract_tables(pdf_a)
    images_a = extract_images(pdf_a)

    logger.info("Extracting from B: %s", pdf_b)
    texts_b = extract_text_pages(pdf_b)
    tables_b = extract_tables(pdf_b)
    images_b = extract_images(pdf_b)

    logger.info("Comparing text")
    text_diffs = compare_texts(texts_a, texts_b)

    logger.info("Comparing tables")
    table_diffs = compare_tables(tables_a, tables_b)

    logger.info("Comparing images")
    image_diffs = compare_images(images_a, images_b)

    return {
        "meta": {"file_a": pdf_a, "file_b": pdf_b},
        "text_diffs": text_diffs,
        "table_diffs": table_diffs,
        "image_diffs": image_diffs,
    }


def main():
    parser = argparse.ArgumentParser(description="Baseline PDF compare tool")
    parser.add_argument("pdf_a", help="Path to first PDF")
    parser.add_argument("pdf_b", help="Path to second PDF")
    parser.add_argument("--out", dest="out", default="report.html", help="Output HTML path")
    args = parser.parse_args()

    report_struct = compare_pdfs(args.pdf_a, args.pdf_b)
    render_html_report(report_struct, args.out)
    logger.info("Report written to %s", args.out)


if __name__ == "__main__":
    main()
