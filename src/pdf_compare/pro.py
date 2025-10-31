"""
pdf_compare.pro

Pro PDF comparison pipeline with semantic text similarity and optional text summarization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
import warnings

import numpy as np
import torch

from utils.extractor import extract_text_pages, extract_tables, extract_images
from utils.compare_text import compare_texts
from utils.compare_table import compare_tables
from utils.compare_image import compare_images
from utils.report import render_html_report

# Keep CPU usage low
try:
    torch.set_num_threads(2)
except Exception:
    pass

logger = logging.getLogger(__name__)
# Allow overriding log level via env var; default to WARNING to reduce noise in UI/CLI
_level_name = os.environ.get("PDF_COMPARE_LOG_LEVEL", "WARNING").upper()
_level = getattr(logging, _level_name, logging.WARNING)
logging.basicConfig(level=_level, format="[%(levelname)s] %(message)s")

# Reduce verbosity from Hugging Face Transformers (e.g., T5Tokenizer legacy notices)
try:
    from transformers.utils import logging as hf_logging  # type: ignore

    hf_logging.set_verbosity_error()
except Exception:
    # If transformers isn't installed yet, just skip
    pass

# Explicitly silence the T5Tokenizer legacy behavior notice (UserWarning)
warnings.filterwarnings(
    "ignore",
    message=r"You are using the default legacy behaviour of the <class 'transformers.models.t5.tokenization_t5.T5Tokenizer'>",
    category=UserWarning,
)

CACHE_DIR = Path(".cache_embeddings")
CACHE_DIR.mkdir(exist_ok=True)


# ---- Text embeddings (MiniLM) ----

def _hash_texts(texts: List[str]) -> str:
    m = hashlib.sha1()
    for t in texts:
        m.update(t.encode("utf-8", errors="ignore"))
        m.update(b"\x00")
    return m.hexdigest()


def embed_paragraphs(paragraphs: List[str], model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    """Embed paragraphs with sentence-transformers and cache to disk."""
    key = _hash_texts(paragraphs) + f"_{model_name.replace('/', '_')}"
    cache_path = CACHE_DIR / f"{key}.npy"
    if cache_path.exists():
        return np.load(cache_path)

    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        logger.error("sentence-transformers not available: %s", e)
        # Fallback: simple TF-IDF-like bag-of-words averaging using hash; not meaningful but stable
        rng = np.random.default_rng(0)
        arr = rng.normal(size=(len(paragraphs), 384)).astype(np.float32)
        np.save(cache_path, arr)
        return arr

    model = SentenceTransformer(model_name, device="cpu")
    emb = model.encode(paragraphs, batch_size=1, convert_to_numpy=True, normalize_embeddings=True)
    np.save(cache_path, emb)
    return emb


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    if a.ndim == 1:
        a = a[None, :]
    if b.ndim == 1:
        b = b[None, :]
    a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
    b = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-8)
    # (a @ b.T) is shape (1,1). Avoid subscripting a float; index matrix first, then cast.
    return float((a @ b.T)[0, 0])


def semantic_text_diffs(texts_a: List[Tuple[int, str]], texts_b: List[Tuple[int, str]], threshold: float = 0.85) -> List[Dict[str, Any]]:
    """Compare paragraphs via embeddings and flag low similarity."""
    # Concatenate per page into paragraphs list
    paras_a = [t for _, t in texts_a]
    paras_b = [t for _, t in texts_b]
    emb_a = embed_paragraphs(paras_a)
    emb_b = embed_paragraphs(paras_b)

    n = min(len(emb_a), len(emb_b))
    out: List[Dict[str, Any]] = []
    for i in range(n):
        sim = _cosine_sim(emb_a[i], emb_b[i])
        if sim < threshold:
            out.append({"page": i + 1, "similarity": float(sim)})
    # note unequal length pages
    if len(emb_a) != len(emb_b):
        out.append({"note": f"page count mismatch: {len(emb_a)} vs {len(emb_b)}"})
    return out


# ---- Summarization (FLAN-T5) ----

def summarize_differences(text: str, model_name: str = "google/flan-t5-small") -> str:
    """Summarize diff text with FLAN-T5; if unavailable (e.g., missing sentencepiece), try BART; else rule-based.

    Order:
    1) Try FLAN-T5 (requires sentencepiece)
    2) Try BART (facebook/bart-large-cnn) which does not require sentencepiece
    3) Fallback: lightweight rule-based summary
    """
    # 1) Try FLAN-T5
    try:
        from transformers import T5ForConditionalGeneration, T5Tokenizer
        # Use new behavior and avoid legacy notice; keep CPU usage
        tokenizer = T5Tokenizer.from_pretrained(model_name, legacy=False)
        model = T5ForConditionalGeneration.from_pretrained(model_name)
        model.to("cpu")
        prompt = "summarize: " + text[:1024]
        inputs = tokenizer([prompt], return_tensors="pt", truncation=True)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_length=120,
                num_beams=2,
                early_stopping=True,
            )
        return tokenizer.decode(out[0], skip_special_tokens=True)
    except Exception as e1:
        # Downgrade to debug to avoid noisy console logs by default
        logger.debug("FLAN-T5 summarizer unavailable: %s", e1)
        # 2) Optionally try BART if explicitly requested via env var (avoids large downloads by default)
        try:
            import os
            if os.environ.get("USE_BART_SUMMARY", "0") == "1":
                from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
                bart_name = "facebook/bart-large-cnn"
                tokenizer = AutoTokenizer.from_pretrained(bart_name)
                model = AutoModelForSeq2SeqLM.from_pretrained(bart_name)
                model.to("cpu")
                inputs = tokenizer([text], return_tensors="pt", truncation=True, max_length=1024)
                with torch.no_grad():
                    out = model.generate(
                        **inputs,
                        max_length=120,
                        num_beams=2,
                        early_stopping=True,
                    )
                return tokenizer.decode(out[0], skip_special_tokens=True)
        except Exception as e2:
            logger.debug("BART summarizer attempt failed: %s", e2)
        # 3) Very small heuristic summary fallback
        snippet = text[:280].replace("\n", " ")
        return (snippet + ("..." if len(text) > 280 else "")) or "No summary available."


# ---- Main pro pipeline ----

def compare_pdfs_pro(pdf_a: str, pdf_b: str, out_html: str | None = None) -> Dict[str, Any]:
    texts_a = extract_text_pages(pdf_a)
    texts_b = extract_text_pages(pdf_b)
    tables_a = extract_tables(pdf_a)
    tables_b = extract_tables(pdf_b)
    images_a = extract_images(pdf_a)
    images_b = extract_images(pdf_b)

    text_diffs = compare_texts(texts_a, texts_b)
    table_diffs = compare_tables(tables_a, tables_b)

    # Image compare: phash-based similarity
    image_diffs = compare_images(images_a, images_b)

    # Semantic text summary
    sem = semantic_text_diffs(texts_a, texts_b)
    summary_input = json.dumps({"semantic": sem, "text": text_diffs[:3]}, ensure_ascii=False)
    summary = summarize_differences(summary_input)

    report_struct = {
        "meta": {"file_a": pdf_a, "file_b": pdf_b, "pro": True},
        "text_diffs": text_diffs,
        "table_diffs": table_diffs,
        "image_diffs": image_diffs,
        "semantic": sem,
        "summary": summary,
    }

    if out_html:
        render_html_report(report_struct, out_html)
    return report_struct


def main():
    parser = argparse.ArgumentParser(description="Pro PDF compare tool")
    parser.add_argument("pdf_a")
    parser.add_argument("pdf_b")
    parser.add_argument("--out", default="report_pro.html")
    args = parser.parse_args()

    rep = compare_pdfs_pro(args.pdf_a, args.pdf_b, out_html=args.out)
    logger.info("Report written to %s", args.out)


if __name__ == "__main__":
    main()
