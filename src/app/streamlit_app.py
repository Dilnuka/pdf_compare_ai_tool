"""
Copilot: Implement a Streamlit web app
- Provide a file uploader for PDF A and PDF B
- When both uploaded, call the baseline or pro pipeline and show:
  - side-by-side PDF preview (first page)
  - Text diffs (collapsible)
  - Table diffs (tables with highlights)
  - Image diffs (thumbnails and similarity)
- Add toggles: 'Use Pro (MiniLM+FLAN+CLIP)' and 'Use CLIP for images'
- Provide a button to download the HTML report
- Keep UI minimal and responsive
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
import streamlit as st

import sys
ROOT = Path(__file__).resolve().parents[2]
src_path = ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from pdf_compare.baseline import compare_pdfs  # type: ignore

st.set_page_config(page_title="PDF Compare", layout="wide")
st.title("AI-Driven PDF Comparison")

col1, col2 = st.columns(2)
with col1:
    file_a = st.file_uploader("Upload PDF A", type=["pdf"], key="pdf_a")
with col2:
    file_b = st.file_uploader("Upload PDF B", type=["pdf"], key="pdf_b")

use_pro = st.toggle("Use Pro (MiniLM + FLAN + optional CLIP)", value=False)
## CLIP removed to simplify the project; only phash image comparison is used

run = st.button("Compare")

if run:
    if not file_a or not file_b:
        st.warning("Please upload both PDFs.")
        st.stop()

    # Save uploaded to temp files
    tmp_dir = Path(".tmp_uploads")
    tmp_dir.mkdir(exist_ok=True)
    path_a = tmp_dir / (file_a.name or "a.pdf")
    path_b = tmp_dir / (file_b.name or "b.pdf")
    path_a.write_bytes(file_a.read())
    path_b.write_bytes(file_b.read())

    if use_pro:
        try:
            from pdf_compare.pro import compare_pdfs_pro  # type: ignore
            report_struct = compare_pdfs_pro(str(path_a), str(path_b), out_html=None)
        except Exception as e:
            st.error(f"Pro pipeline failed ({e}); falling back to baseline.")
            report_struct = compare_pdfs(str(path_a), str(path_b))
    else:
        report_struct = compare_pdfs(str(path_a), str(path_b))

    st.success("Comparison complete.")

    # Show sections
    with st.expander("Text differences", expanded=False):
        for d in report_struct.get("text_diffs", []):
            st.subheader(f"Scope: {d.get('scope')} Page: {d.get('page')}")
            st.code(d.get("diff_snippet", ""))

    with st.expander("Table differences", expanded=False):
        for t in report_struct.get("table_diffs", []):
            st.write(f"Page {t.get('page')} | A {t.get('table_A_shape')} vs B {t.get('table_B_shape')}")
            diffs = t.get("cell_diffs_sample") or []
            if diffs:
                st.table(diffs)
            else:
                st.write("No differences or tables missing.")

    with st.expander("Image differences", expanded=False):
        imgs = report_struct.get("image_diffs", {})
        for m in imgs.get("matches", []):
            st.write(f"Match distance: {m.get('distance')}")
            ca, cb = st.columns(2)
            with ca:
                st.image(f"data:image/png;base64,{m['A'].thumbnail_b64}")
            with cb:
                st.image(f"data:image/png;base64,{m['B'].thumbnail_b64}")
        if imgs.get("unmatched_A"):
            st.write("Unmatched A:")
            st.image([f"data:image/png;base64,{a.thumbnail_b64}" for a in imgs["unmatched_A"]])
        if imgs.get("unmatched_B"):
            st.write("Unmatched B:")
            st.image([f"data:image/png;base64,{b.thumbnail_b64}" for b in imgs["unmatched_B"]])

    # Download HTML report
    from utils.report import render_html_report  # type: ignore

    html = render_html_report(report_struct, out_path=None)
    st.download_button(
        label="Download HTML report",
        data=html,
        file_name="report.html",
        mime="text/html",
    )
