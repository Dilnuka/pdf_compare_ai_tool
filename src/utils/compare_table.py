"""
Copilot: Implement table comparison utilities:
- function compare_tables(tables_a, tables_b)
- match tables by page, then shape, then produce a sample of cell diffs
- output list of dicts: {'page', 'table_A_shape','table_B_shape','cell_diffs_sample'}
"""

from __future__ import annotations

from typing import List, Tuple, Dict
import pandas as pd


def compare_tables(
    tables_a: List[Tuple[int, pd.DataFrame]],
    tables_b: List[Tuple[int, pd.DataFrame]],
    sample_limit: int = 30,
) -> List[Dict]:
    results: List[Dict] = []

    # Group by page
    by_page_a: Dict[int, List[pd.DataFrame]] = {}
    by_page_b: Dict[int, List[pd.DataFrame]] = {}
    for p, df in tables_a:
        by_page_a.setdefault(p, []).append(df)
    for p, df in tables_b:
        by_page_b.setdefault(p, []).append(df)

    all_pages = sorted(set(by_page_a) | set(by_page_b))
    for p in all_pages:
        list_a = by_page_a.get(p, [])
        list_b = by_page_b.get(p, [])
        max_len = max(len(list_a), len(list_b))
        for i in range(max_len):
            df_a = list_a[i] if i < len(list_a) else pd.DataFrame()
            df_b = list_b[i] if i < len(list_b) else pd.DataFrame()

            diffs = []
            if not df_a.empty and not df_b.empty and df_a.shape == df_b.shape:
                # Same shape -> compare cells
                rows, cols = df_a.shape
                count = 0
                for r in range(rows):
                    for c in range(cols):
                        va = str(df_a.iat[r, c])
                        vb = str(df_b.iat[r, c])
                        if va != vb:
                            diffs.append({"row": r, "col": c, "A": va, "B": vb})
                            count += 1
                            if count >= sample_limit:
                                break
                    if count >= sample_limit:
                        break
            else:
                # Different shape or one missing
                diffs.append(
                    {
                        "note": "shape mismatch or missing table",
                        "A_shape": tuple(df_a.shape),
                        "B_shape": tuple(df_b.shape),
                    }
                )

            results.append(
                {
                    "page": p,
                    "table_A_shape": tuple(df_a.shape),
                    "table_B_shape": tuple(df_b.shape),
                    "cell_diffs_sample": diffs,
                }
            )

    return results
