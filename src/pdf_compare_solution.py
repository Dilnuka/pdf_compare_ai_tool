"""
Baseline PDF comparison with optional AI summarization (Gemini 2.0 Flash).
- Text, table, image comparisons using utils.
- AI summary generator that reads prompt.md (if present) or uses a built-in enterprise prompt.
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
    """Run baseline comparison across text, tables, and images."""
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
    """
    Generate AI-powered comparison summary using Gemini.

    Args:
        pdf_a_path: Path to first PDF
        pdf_b_path: Path to second PDF
        api_key: Google API key (if None, will try to get from env/.env)
    Returns:
        Formatted comparison summary from Gemini
    """
    try:
        import google.generativeai as genai
    except ImportError:
        logger.error("google-generativeai package not installed. Install with: pip install google-generativeai")
        return "Error: google-generativeai package not installed."

    # Resolve API key
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
        return "Error: Google API key not found. Please set GOOGLE_API_KEY environment variable."

    try:
        # Configure Gemini
        genai.configure(api_key=api_key)

        # Extract and (optionally) limit text
        logger.info("Extracting text from PDFs for AI summarization...")
        texts_a_all = extract_text_pages(pdf_a_path)
        texts_b_all = extract_text_pages(pdf_b_path)
        texts_a = texts_a_all[:page_limit] if page_limit else texts_a_all
        texts_b = texts_b_all[:page_limit] if page_limit else texts_b_all

        pdf_a_text = "\n\n".join([f"Page {i+1}:\n{text}" for i, text in enumerate(texts_a)])
        pdf_b_text = "\n\n".join([f"Page {i+1}:\n{text}" for i, text in enumerate(texts_b)])

        if max_chars_per_doc and isinstance(max_chars_per_doc, int):
            if len(pdf_a_text) > max_chars_per_doc:
                pdf_a_text = pdf_a_text[:max_chars_per_doc]
            if len(pdf_b_text) > max_chars_per_doc:
                pdf_b_text = pdf_b_text[:max_chars_per_doc]

        # Load external prompt if available
        prompt_template: Optional[str] = None
        try:
            prompt_path = Path.cwd() / "prompt.md"
            if prompt_path.exists():
                prompt_template = prompt_path.read_text(encoding="utf-8")
        except Exception:
            prompt_template = None

        if not prompt_template:
            # Built-in enterprise-grade prompt (kept in sync with prompt.md structure)
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
| Material Category | Product Only | Primary Pack | Secondary Pack |
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

        logger.error("Retries exhausted generating AI summary: %s", last_err)
        return (
            "Error generating AI summary: 429 Resource exhausted or rate-limited. "
            "Tips: Try again in a minute or try again with smaller documents."
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
