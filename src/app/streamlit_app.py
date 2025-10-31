"""
Streamlit web app (sidebar navigation)
- Left sidebar like ChatGPT: switch between Basic and Pro pages.
- Each page has its own uploaders and Compare action.
- Recent reports are stored in session_state and shown in the sidebar.
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

st.set_page_config(page_title="PDF Compare", page_icon="🧾", layout="wide")

# --- Session state ---
if "reports" not in st.session_state:
    st.session_state.reports = []  # list of {title, html}

# --- Sidebar (navigation + reports) ---
st.sidebar.title("🧾 PDF Compare")

# Size preset for the dropzones so the first screen fits nicely
size_preset = st.sidebar.selectbox(
    "Upload area size",
    options=["Compact", "Comfortable", "Spacious"],
    index=1,
    help="Adjust the height of the drag-and-drop boxes to your screen."
)
_HEIGHT_MAP = {"Compact": "28vh", "Comfortable": "40vh", "Spacious": "60vh"}
dz_height = _HEIGHT_MAP.get(size_preset, "40vh")

# Navigation after size selector
page = st.sidebar.radio("Navigation", ["Basic", "Pro"])

# Inject CSS with the chosen height (placed after sidebar to override defaults)
st.markdown(
        f"""
        <style>
            /* Streamlit: file-uploader dropzones with user-selectable height */
            div[data-testid="stFileUploadDropzone"],
            section[data-testid="stFileUploadDropzone"],
            div[data-testid="stFileUploaderDropzone"],
            section[data-testid="stFileUploaderDropzone"],
            div[data-testid="stFileUploader"] section {{
                min-height: {dz_height} !important;
                border: 2px dashed #cbd5e1 !important;
                border-radius: 12px !important;
                transition: min-height .2s ease-in-out;
            }}
            div[data-testid="stFileUploadDropzone"] > div,
            section[data-testid="stFileUploadDropzone"] > div,
            div[data-testid="stFileUploaderDropzone"] > div,
            section[data-testid="stFileUploaderDropzone"] > div,
            div[data-testid="stFileUploader"] section > div {{
                padding: 28px 16px !important;
            }}
            div[data-testid="stFileUploadDropzone"] section,
            section[data-testid="stFileUploadDropzone"] section,
            div[data-testid="stFileUploaderDropzone"] section,
            section[data-testid="stFileUploaderDropzone"] section,
            div[data-testid="stFileUploader"] section section {{
                min-height: calc({dz_height} - 40px) !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                flex-direction: column !important;
            }}
            div[data-testid="stFileUploadDropzone"] section div,
            section[data-testid="stFileUploadDropzone"] section div,
            div[data-testid="stFileUploaderDropzone"] section div,
            section[data-testid="stFileUploaderDropzone"] section div,
            div[data-testid="stFileUploader"] section section div {{
                font-size: 1.06rem !important;
            }}
            div[data-testid="stFileUploadDropzone"] svg,
            section[data-testid="stFileUploadDropzone"] svg,
            div[data-testid="stFileUploaderDropzone"] svg,
            section[data-testid="stFileUploaderDropzone"] svg,
            div[data-testid="stFileUploader"] section svg {{
                width: 48px !important; height: 48px !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
)

st.sidebar.markdown("---")
st.sidebar.markdown("#### Recent reports")
if not st.session_state.reports:
    st.sidebar.caption("No reports yet.")
else:
    for i, rep in enumerate(st.session_state.reports[:5]):
        st.sidebar.download_button(
            key=f"sdl_{i}", label=rep["title"], data=rep["html"], file_name=rep["title"], mime="text/html"
        )


def _render_results(report_struct):
    with st.expander("Text differences", expanded=False):
        for d in report_struct.get("text_diffs", []):
            scope = d.get('scope', 'page')
            page = d.get('page', '-')
            st.subheader(f"Scope: {scope} | Page: {page}")
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
            st.write(f"pHash distance: {m.get('distance')}")
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


def _compare_flow(use_pro: bool):
    st.markdown("### Upload and compare")
    # Side-by-side, large dropzones (CSS above increases min-height)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        file_a = st.file_uploader(
            "Upload PDF A",
            type=["pdf"],
            key=("pdf_a_pro" if use_pro else "pdf_a_basic"),
            help="Drag & drop your first PDF here or click to browse.",
        )
    with c2:
        file_b = st.file_uploader(
            "Upload PDF B",
            type=["pdf"],
            key=("pdf_b_pro" if use_pro else "pdf_b_basic"),
            help="Drag & drop your second PDF here or click to browse.",
        )

    # Centered Compare button row
    spacer_left, center_col, spacer_right = st.columns([1, 0.6, 1])
    with center_col:
        compare_btn = st.button(
            "Compare",
            type="primary",
            use_container_width=True,
            key=("cmp_pro" if use_pro else "cmp_basic"),
        )

    # compare_btn already defined above in the centered column
    if compare_btn:
        if not file_a or not file_b:
            st.warning("Please upload both PDFs.")
            st.stop()
        tmp_dir = Path(".tmp_uploads")
        tmp_dir.mkdir(exist_ok=True)
        path_a = tmp_dir / (file_a.name or "a.pdf")
        path_b = tmp_dir / (file_b.name or "b.pdf")
        path_a.write_bytes(file_a.read())
        path_b.write_bytes(file_b.read())
        with st.spinner("Comparing… This may take a moment."):
            if use_pro:
                try:
                    from pdf_compare.pro import compare_pdfs_pro  # type: ignore
                    report_struct = compare_pdfs_pro(str(path_a), str(path_b), out_html=None)
                except Exception as e:
                    st.error(f"Pro pipeline failed ({e}); falling back to Basic.")
                    report_struct = compare_pdfs(str(path_a), str(path_b))
            else:
                report_struct = compare_pdfs(str(path_a), str(path_b))
        st.success("Comparison complete.")
        _render_results(report_struct)
        from utils.report import render_html_report  # type: ignore
        html = render_html_report(report_struct, out_path=None)
        fname = f"report_{Path(file_a.name).stem}_vs_{Path(file_b.name).stem}.html"
        st.download_button(label="Download HTML report", data=html, file_name=fname, mime="text/html")
        st.session_state.reports.insert(0, {"title": fname, "html": html})
        st.session_state.reports = st.session_state.reports[:10]


# --- Page routing ---
st.title(f"AI‑Driven PDF Comparison · {page}")
if page == "Basic":
    st.caption("Quick diffs for text, tables, and images using pHash")
    _compare_flow(use_pro=False)
else:
    st.caption("Semantic text diffs (MiniLM) and optional summaries")
    _compare_flow(use_pro=True)
