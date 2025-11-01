"""
Copilot: Implement a baseline PDF comparison script.
Requirements:
- Extract text (PyMuPDF) from two PDFs.
- Extract tables (pdfplumber) and convert to pandas DataFrame.
- Extract images (PyMuPDF) and save them as PNG in /tmp or memory.
- Compare text using difflib and produce a short unified_diff snippet per page.
- Compare tables by page and produce cell-level differences (sample up to 30).
- Compare images using imagehash phash and output hamming distance.
- Render an HTML report using Jinja2 that includes: file names, text diffs, table diffs, image diffs (base64 thumbnails).
- Provide a main() CLI that accepts two pdf file paths and an optional output HTML path.
- Add helpful docstrings, logging, and safe error handling.
- Add AI summarization using Gemini API to generate comparison summaries.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from typing import Dict, Any, Optional

from utils.extractor import extract_text_pages, extract_tables, extract_images
from pathlib import Path
import re
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
        "texts_a": texts_a,  # Store for AI summarization
        "texts_b": texts_b,  # Store for AI summarization
    }


def generate_ai_summary(
    pdf_a_path: str,
    pdf_b_path: str,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash",
    page_limit: Optional[int] = 20,
    max_chars_per_doc: Optional[int] = 20000,
    retries: int = 3,
    backoff_base: float = 2.0,
) -> str:
    """
    Generate AI-powered comparison summary using Gemini 2.0 Flash.
    
    Args:
        pdf_a_path: Path to first PDF
        pdf_b_path: Path to second PDF
        api_key: Google API key (if None, will try to get from GOOGLE_API_KEY env var)
    
    Returns:
        Formatted comparison summary from Gemini
    """
    try:
        import google.generativeai as genai
    except ImportError:
        logger.error("google-generativeai package not installed. Install with: pip install google-generativeai")
        return "Error: google-generativeai package not installed."
    
    # Get API key
    if api_key is None:
        # Try environment first
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            # Attempt to load from .env/.env.local, then .env.example (dev fallback)
            try:
                from dotenv import load_dotenv
                from pathlib import Path
                root = Path.cwd()
                for fname in (".env.local", ".env"):
                    fp = root / fname
                    if fp.exists():
                        load_dotenv(dotenv_path=str(fp), override=False)
                        api_key = os.getenv("GOOGLE_API_KEY")
                        if api_key:
                            break
                if not api_key:
                    ex = root / ".env.example"
                    if ex.exists():
                        load_dotenv(dotenv_path=str(ex), override=False)
                        api_key = os.getenv("GOOGLE_API_KEY")
            except Exception:
                # dotenv not installed; continue with whatever is set
                pass
    
    if not api_key:
        logger.error("Google API key not found. Set GOOGLE_API_KEY environment variable.")
        return "Error: Google API key not found. Please set GOOGLE_API_KEY environment variable."
    
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        
    # Extract all text from both PDFs
        logger.info("Extracting text from PDFs for AI summarization...")
    texts_a_all = extract_text_pages(pdf_a_path)
    texts_b_all = extract_text_pages(pdf_b_path)

    # Optionally limit number of pages to reduce tokens / cost
    texts_a = texts_a_all[:page_limit] if page_limit else texts_a_all
    texts_b = texts_b_all[:page_limit] if page_limit else texts_b_all
        
        # Combine all pages text
        pdf_a_text = "\n\n".join([f"Page {i+1}:\n{text}" for i, text in enumerate(texts_a)])
        pdf_b_text = "\n\n".join([f"Page {i+1}:\n{text}" for i, text in enumerate(texts_b)])

        # Optionally trim by characters (safety guard)
        if max_chars_per_doc and isinstance(max_chars_per_doc, int):
            if len(pdf_a_text) > max_chars_per_doc:
                pdf_a_text = pdf_a_text[:max_chars_per_doc]
            if len(pdf_b_text) > max_chars_per_doc:
                pdf_b_text = pdf_b_text[:max_chars_per_doc]
        
        # Load the prompt template: prefer prompt.md in project root, fallback to built-in template
        prompt_template = None
        try:
            prompt_path = Path.cwd() / "prompt.md"
            if prompt_path.exists():
                raw = prompt_path.read_text(encoding="utf-8")
                # If the file contains a Python f-string wrapper, extract inside triple quotes
                m = re.search(r"^[\s\S]*?"""([\s\S]*?)"""", raw)
                if m:
                    prompt_template = m.group(1)
                else:
                    prompt_template = raw
        except Exception:
            prompt_template = None

        if not prompt_template:
            # Built-in improved template (kept in sync with prompt.md)
            prompt_template = (
                "You are a Technical Product Analyst. Analyze and compare two product specification PDFs and produce an "
                "enterprise-grade, structured engineering comparison suitable for business stakeholders and panel review.\n\n"
                "INPUTS\nPDF A Content:\n{pdf_a_text}\n\nPDF B Content:\n{pdf_b_text}\n\n"
                "TONE & STYLE\n- Clear, professional business English; confident, analytical voice\n- No repetition or informal wording\n- Do not hallucinate: only use information found in the provided PDFs\n\n"
                "STRUCTURE (follow exactly in this order)\n\n# ✅ Automated Comparison Summary — Product Specification Docs\n\n"
                "## Document Overview\nProvide a table with the following fields when available. If a value is missing, write \"Not specified\".\n"
                "| Field | Product A | Product B |\n|---|---|---|\n| Brand |  |  |\n| Product Code |  |  |\n| Description |  |  |\n| Barcode |  |  |\n| Commodity Code |  |  |\n| Country of Origin |  |  |\n| Document Template / Source |  |  |\n\n"
                "## Feature & Function Comparison\nCompare design intent, functional differences, material choices, and performance features. Use concise engineering language.\n"
                "| Category | Product A | Product B |\n|---|---|---|\n\n"
                "## Dimensional & Packaging Comparison\nExtract numeric values with units when present (mm, g, pcs). Do not invent units; if none are specified, write \"Not specified\". "
                "Use arrows for change: ↑ increase, ↓ decrease, = equal.\n"
                "| Attribute | Product A | Product B | Change (↑/↓/=) |\n|---|---|---|---|\n| Width |  |  |  |\n| Height |  |  |  |\n| Depth |  |  |  |\n| Weight |  |  |  |\n| Packaging Quantity |  |  |  |\n| Packaging Materials (Plastic/Cardboard) |  |  |  |\n\n"
                "## Key Insights\nProvide 4–8 engineering and business insights as polished bullets using the • symbol. Address:\n"
                "• Functional differences and their implications (strength, precision, durability)\n"
                "• Material choices and trade-offs (e.g., alloy vs. carbon steel)\n"
                "• Usability/ergonomics when present (handle design, grip, safety)\n"
                "• Compliance standards if detected (e.g., RoHS, CE)\n"
                "• Supply chain/manufacturing origin differences and implications\n"
                "• Packaging strategy (bulk vs retail) and sustainability (plastic use vs none)\n"
                "• Logistics considerations: weight/volume effects on shipping/storage\n\n"
                "## Executive Summary\n3–5 concise lines in professional business English summarizing the real-world implications "
                "for product selection, application, and procurement.\n\n"
                "ACCURACY & QUALITY RULES\n- Never invent specifications; only use what appears in the PDFs\n"
                "- Mark missing information as \"Not specified\"\n- Normalize obvious OCR/spacing issues (fix broken words/spacing)\n"
                "- Replace generic list markers with proper bullets (•) in outputs\n- Ensure all numeric values show units if present in the source; otherwise mark as \"Not specified\"\n"
                "- Keep Product A and Product B labels consistent across all sections\n- Ensure tables are properly aligned and readable; fix misaligned rows/columns in output formatting\n"
                "- Do not mention these rules or that you are an AI\n\n"
                "GOAL\nDeliver a clean, polished, and accurate engineering comparison with supply chain and logistics context, ready for business stakeholders.\n\n"
                "Return ONLY the formatted comparison above, nothing else."
            )

        # Format the prompt with actual PDF content
        try:
            full_prompt = prompt_template.format(pdf_a_text=pdf_a_text, pdf_b_text=pdf_b_text)
        except Exception:
            # If braces cause formatting issues, do a minimal replacement
            full_prompt = prompt_template.replace("{pdf_a_text}", pdf_a_text).replace("{pdf_b_text}", pdf_b_text)
        
        # Create model and generate
        logger.info("Generating AI summary using %s...", model_name)
        model = genai.GenerativeModel(model_name)

        last_err: Optional[Exception] = None
        for attempt in range(1, max(1, retries) + 1):
            try:
                response = model.generate_content(full_prompt)
                logger.info("AI summary generated successfully")
                return response.text
            except Exception as e:
                msg = str(e)
                last_err = e
                # Handle rate-limit / resource exhausted with backoff
                if "429" in msg or "Resource exhausted" in msg or "quota" in msg.lower():
                    wait_s = (backoff_base ** (attempt - 1))
                    logger.warning(
                        "Gemini API rate limit hit (attempt %s/%s). Backing off for %.1fs...",
                        attempt,
                        retries,
                        wait_s,
                    )
                    time.sleep(wait_s)
                    continue
                else:
                    logger.error("Non-retryable error generating AI summary: %s", e)
                    return f"Error generating AI summary: {msg}"

        # If we got here, retries exhausted
        logger.error("Retries exhausted generating AI summary: %s", last_err)
        return (
            "Error generating AI summary: 429 Resource exhausted or rate-limited. "
            "Tips: Try again in a minute, reduce 'AI pages used' in options, or switch models."
        )
        
    except Exception as e:
        logger.error(f"Error generating AI summary: {e}")
        return f"Error generating AI summary: {str(e)}"


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
