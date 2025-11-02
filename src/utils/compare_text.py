"""
Copilot: Implement text comparison utilities:
- function compare_texts(texts_a, texts_b) that handles:
  - if page counts match: page-by-page diffs using difflib.unified_diff
  - if mismatch: full-document diff
- returns structured results: list of dicts {'scope', 'page', 'diff_snippet'}
- include parameter to limit diff size
"""

from __future__ import annotations

import difflib
from typing import List, Tuple, Dict


def _limit_lines(lines: List[str], max_lines: int) -> List[str]:
    if len(lines) <= max_lines:
        return lines
    head = lines[: max_lines // 2]
    tail = lines[-max_lines // 2 :]
    return head + ["... (diff truncated) ...\n"] + tail


def compare_texts(
    texts_a: List[Tuple[int, str]],
    texts_b: List[Tuple[int, str]],
    max_diff_lines: int = 60,
) -> List[Dict]:
    results: List[Dict] = []

    if len(texts_a) == len(texts_b):
        for (pa, ta), (pb, tb) in zip(texts_a, texts_b):
            diff = difflib.unified_diff(
                ta.splitlines(keepends=True),
                tb.splitlines(keepends=True),
                fromfile=f"A:page{pa}",
                tofile=f"B:page{pb}",
                n=3,
            )
            diff_lines = list(diff)
            diff_lines = _limit_lines(diff_lines, max_diff_lines)
            results.append(
                {
                    "scope": "page",
                    "page": pa,
                    "diff_snippet": "".join(diff_lines),
                }
            )
    else:
        doc_a = "\n".join(t for _, t in texts_a)
        doc_b = "\n".join(t for _, t in texts_b)
        diff = difflib.unified_diff(
            doc_a.splitlines(keepends=True),
            doc_b.splitlines(keepends=True),
            fromfile="A:full",
            tofile="B:full",
            n=3,
        )
        diff_lines = list(diff)
        diff_lines = _limit_lines(diff_lines, max_diff_lines)
        results.append({"scope": "full", "page": None, "diff_snippet": "".join(diff_lines)})

    return results
