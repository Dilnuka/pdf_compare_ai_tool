"""
PDF Comparison Tool

Compares two PDF files and generates comparison reports.
Supports text, table, and image diff analysis with optional AI summaries.

Author: Dilnuka
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from utils.extractor import extract_text_pages, extract_tables, extract_images
from utils.compare_text import compare_texts
from utils.compare_table import compare_tables
from utils.compare_image import compare_images
from utils.report import render_html_report

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def compare_pdfs(pdf_a: str, pdf_b: str) -> Dict[str, Any]:
    """Compare two PDFs and return detailed differences."""
    logger.info("Extracting from A: %s", pdf_a)
    texts_a = extract_text_pages(pdf_a)
    tables_a = extract_tables(pdf_a)
    images_a = extract_images(pdf_a)

    logger.info("Extracting from B: %s", pdf_b)
    texts_b = extract_text_pages(pdf_b)
    tables_b = extract_tables(pdf_b)
    images_b = extract_images(pdf_b)

    # Compare all content types
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


def generate_ai_summary(
    pdf_a_path: str,
    pdf_b_path: str,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash",
    page_limit: Optional[int] = None,
    max_chars_per_doc: Optional[int] = 20000,
    retries: int = 3,
    backoff_base: float = 2.0,
) -> str:
    """Generate AI summary using Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        logger.error("Missing google-generativeai package")
        return "Error: google-generativeai not installed."

    # Get API key from env
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            try:
                from dotenv import load_dotenv
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
                pass

    if not api_key:
        return "Error: GOOGLE_API_KEY not found in environment."

    try:
        genai.configure(api_key=api_key)

        logger.info("Extracting text for AI analysis...")
        texts_a_all = extract_text_pages(pdf_a_path)
        texts_b_all = extract_text_pages(pdf_b_path)
        
        # Apply page limit if specified
        texts_a = texts_a_all[:page_limit] if page_limit else texts_a_all
        texts_b = texts_b_all[:page_limit] if page_limit else texts_b_all

        pdf_a_text = "\n\n".join([f"Page {i+1}:\n{text}" for i, text in enumerate(texts_a)])
        pdf_b_text = "\n\n".join([f"Page {i+1}:\n{text}" for i, text in enumerate(texts_b)])

        # Truncate to avoid hitting API limits
        if max_chars_per_doc and isinstance(max_chars_per_doc, int):
            if len(pdf_a_text) > max_chars_per_doc:
                pdf_a_text = pdf_a_text[:max_chars_per_doc]
            if len(pdf_b_text) > max_chars_per_doc:
                pdf_b_text = pdf_b_text[:max_chars_per_doc]

        # Load prompt template
        prompt_template: Optional[str] = None
        try:
            prompt_path = Path.cwd() / "prompt.md"
            if prompt_path.exists():
                prompt_template = prompt_path.read_text(encoding="utf-8")
        except Exception:
            pass

        if not prompt_template:
            prompt_template = """
You are a Technical Product Analyst. Analyze and compare two product specification PDFs and produce an enterprise-grade, structured engineering comparison suitable for business stakeholders and interview panel review.

INPUTS
PDF A Content:
{pdf_a_text}

PDF B Content:
{pdf_b_text}

TONE & STYLE
- Clear, professional business English; confident and analytical tone
- Fact-driven, concise, structured technical language
- Natural enterprise reporting tone (not chatty or conversational)
- Do not repeat content, avoid filler language

STRICT ACCURACY RULES
- Do not hallucinate. Only use information present in the PDFs
- If a field is missing, use: Not specified
- Correct OCR/spacing issues if needed
- Preserve units (mm, g, kg, pcs) when present
- Do not invent units; if unit missing, mark: Not specified
- Never add features or data not explicitly shown
- Convert "-" or blank values to: None
- Ensure clean, aligned tables — no formatting glitches
- Do NOT split Product A and Product B into separate tables; always use a single table with columns "Product A" and "Product B" where applicable
- For long content inside table cells, keep it in the same cell; use concise phrases and insert line breaks (e.g., <br>) between items if needed (do not create extra tables)

OUTPUT FORMAT
(return EXACTLY in this structure)

# ✅ Automated Comparison Summary — Product Specification Docs

## Document Overview
| Field | Product A | Product B |
|---|---|---|
| Brand |  |  |
| Product Code |  |  |
| Description |  |  |
| Barcode |  |  |
| Commodity Code |  |  |
| Country of Origin |  |  |
| Document Template / Source |  |  |

## Feature & Function Comparison
| Category | Product A | Product B |
|---|---|---|
| Tool Type |  |  |
| Primary Function |  |  |
| Material |  |  |
| Key Features |  |  |
| Design Focus |  |  |

• Provide 2–3 bullet insights under this table

## Dimensional Comparison (Product Only)
| Dimension / Weight | Product A | Product B | Change (↑/↓/=) |
|---|---|---|---|
| Width |  |  |  |
| Height/Length |  |  |  |
| Depth |  |  |  |
| Weight |  |  |  |

## Packaging — Weights & Measures
| Attribute | Product Only | Primary Pack | Secondary Pack | Transit Pack |
|---|---|---|---|---|
| Quantity |  |  |  |  |
| Width |  |  |  |  |
| Depth |  |  |  |  |
| Height |  |  |  |  |
| Weight |  |  |  |  |

## Packaging — Materials
| Material Category | Primary Pack | Secondary | Transit Pack |
|---|---|---|---|
| Card Use |  |  |  |
| Card Weight |  |  |  |
| Plastic Use |  |  |  |
| Plastic Weight |  |  |  |
| Metal Use |  |  |  |
| Metal Weight |  |  |  |
| Timber Use |  |  |  |
| Timber Weight |  |  |  |

## Key Insights
Provide 6–10 bullet points using the • symbol. Address:
• Functional and engineering differences  
• Material selection rationale (strength, precision, durability)  
• Ergonomics and handling (if relevant)  
• Standards/compliance mentions (if any exist)  
• Supply chain & country-of-origin implications  
• Packaging strategy (bulk vs retail)  
• Sustainability trade-offs (plastic vs no-plastic)  
• Logistics considerations (weight & volume impact on shipping storage)

## Executive Summary
3–5 polished business lines summarizing:
- Core performance differences
- User/application context
- Packaging & supply chain implications
- Procurement impact

GOAL
Deliver a clean, accurate, business-ready engineering comparison suitable for a professional demo and interview panel.
Return ONLY the formatted comparison — no explanation, no extra text.
"""

        try:
            full_prompt = prompt_template.format(pdf_a_text=pdf_a_text, pdf_b_text=pdf_b_text)
        except Exception:
            full_prompt = prompt_template.replace("{pdf_a_text}", pdf_a_text).replace("{pdf_b_text}", pdf_b_text)

        # Call Gemini with retry logic
        model = genai.GenerativeModel(model_name)
        last_err = None
        
        for attempt in range(1, retries + 1):
            try:
                response = model.generate_content(full_prompt)
                logger.info("Summary generated")
                return response.text
            except Exception as e:
                last_err = e
                msg = str(e)
                
                # Check if it's a rate limit error
                if "429" in msg or "Resource exhausted" in msg or "quota" in msg.lower():
                    wait_time = backoff_base ** (attempt - 1)
                    logger.warning(f"Rate limited. Retrying in {wait_time}s... (attempt {attempt}/{retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API error: {e}")
                    return f"Error: {msg}"

        return f"Error: Rate limit exceeded. Try again later. ({last_err})"

    except Exception as e:
        logger.error(f"AI summary failed: {e}")
        return f"Error: {str(e)}"


def merge_side_by_side_comparison(
    pdf_a: str,
    pdf_b: str,
    out: Optional[str] = None,
    highlight: bool = False,
    max_pages: Optional[int] = None,
) -> str:
    """Merge two PDFs side-by-side for visual comparison."""
    try:
        from pdf_compare.visual import (
            merge_side_by_side,
            merge_side_by_side_with_text_highlight,
        )
    except ImportError:
        logger.error("pdf_compare.visual module missing")
        raise ImportError("Visual comparison module not found.")
    
    out_path = out or ("side_by_side_highlighted.pdf" if highlight else "side_by_side.pdf")
    logger.info(f"Creating side-by-side PDF (highlight={highlight})")
    if highlight:
        merge_side_by_side_with_text_highlight(pdf_a, pdf_b, out_path=out_path, max_pages=max_pages)
    else:
        merge_side_by_side(pdf_a, pdf_b, out_path=out_path, max_pages=max_pages)
    
    logger.info(f"Created: {out_path}")
    return out_path


def main():
    """CLI for PDF comparison tool."""
    parser = argparse.ArgumentParser(description="PDF Comparison Tool")
    parser.add_argument("pdf_a", help="Path to first PDF")
    parser.add_argument("pdf_b", help="Path to second PDF")
    parser.add_argument("--out", help="Output file path")
    
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--ai-summary", action="store_true", help="Generate AI summary")
    mode_group.add_argument("--side-by-side", action="store_true", help="Side-by-side visual comparison")
    
    parser.add_argument("--highlight", action="store_true", help="Highlight differences")
    parser.add_argument("--max-pages", type=int, help="Limit pages")
    
    args = parser.parse_args()
    
    if args.ai_summary:
        summary = generate_ai_summary(args.pdf_a, args.pdf_b)
        if args.out:
            Path(args.out).write_text(summary, encoding="utf-8")
            logger.info(f"Saved to {args.out}")
        else:
            print(summary)
    
    elif args.side_by_side:
        out_path = merge_side_by_side_comparison(
            args.pdf_a, args.pdf_b,
            out=args.out,
            highlight=args.highlight,
            max_pages=args.max_pages
        )
        logger.info(f"Created {out_path}")
    
    else:
        report_struct = compare_pdfs(args.pdf_a, args.pdf_b)
        out_path = args.out or "report.html"
        render_html_report(report_struct, out_path)
        logger.info(f"Report saved to {out_path}")


if __name__ == "__main__":
    main()
