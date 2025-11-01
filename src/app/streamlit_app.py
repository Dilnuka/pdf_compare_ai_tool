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
import fitz  # PyMuPDF

import sys
ROOT = Path(__file__).resolve().parents[2]
src_path = ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from pdf_compare.baseline import compare_pdfs  # type: ignore
from pdf_compare.visual import (
    merge_side_by_side,
    render_page_pair_png_highlight,
    merge_side_by_side_with_text_highlight,
)  # type: ignore

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

# Navigation after size selector (two modes only)
page = st.sidebar.radio("Navigation", ["Basic", "Pro (Side‑by‑Side)"])

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


@st.cache_data(show_spinner=False)
def _render_png_bytes(pdf_bytes: bytes, page_index: int, zoom: float = 1.8) -> bytes:
    """Cache-friendly rendering of a PDF page to PNG bytes for Streamlit display."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        p = doc[page_index]
        pix = p.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")


def _side_by_side_flow():
    st.markdown("### Visual side‑by‑side comparison")
    mode = st.radio("Mode", ["Visual", "Compare Text"], horizontal=True, key="ss_mode")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        file_a = st.file_uploader("Upload PDF A", type=["pdf"], key="pdf_a_visual")
    with c2:
        file_b = st.file_uploader("Upload PDF B", type=["pdf"], key="pdf_b_visual")

    if file_a and file_b:
        bytes_a = file_a.read()
        bytes_b = file_b.read()
        with fitz.open(stream=bytes_a, filetype="pdf") as da, fitz.open(stream=bytes_b, filetype="pdf") as db:
            total = min(len(da), len(db))
        st.caption(f"Showing {total} paired pages")
        if total > 1:
            pg = st.slider("Page", 1, total, 1, key="page_visual")
        else:
            pg = 1
        z = st.select_slider("Zoom", options=[1.2, 1.5, 1.8, 2.0, 2.5, 3.0], value=1.8, key="zoom_visual")
        ca, cb = st.columns(2, gap="large")
        with st.spinner("Rendering page images…"):
            if mode == "Visual":
                img_a = _render_png_bytes(bytes_a, pg - 1, z)
                img_b = _render_png_bytes(bytes_b, pg - 1, z)
            else:
                img_a, img_b = render_page_pair_png_highlight(bytes_a, bytes_b, pg - 1, zoom=z)
        with ca:
            st.image(img_a, caption=f"A · Page {pg}", width='stretch')
        with cb:
            st.image(img_b, caption=f"B · Page {pg}", width='stretch')

        st.markdown("#### Export")
        colx, coly = st.columns([1, 1])
        with colx:
            if mode == "Visual":
                if st.button("Merge all pages side‑by‑side (download)", type="primary", key="merge_visual"):
                    with st.spinner("Merging PDFs…"):
                        merged = merge_side_by_side(bytes_a, bytes_b)
                    st.download_button(
                        label="Download merged PDF",
                        data=merged,
                        file_name=f"merged_{Path(file_a.name).stem}_vs_{Path(file_b.name).stem}.pdf",
                        mime="application/pdf",
                    )
            else:
                if st.button("Merge with text highlights (download)", type="primary", key="merge_visual_diff"):
                    with st.spinner("Merging and highlighting differences…"):
                        merged = merge_side_by_side_with_text_highlight(bytes_a, bytes_b)
                    st.download_button(
                        label="Download highlighted PDF",
                        data=merged,
                        file_name=f"merged_diff_{Path(file_a.name).stem}_vs_{Path(file_b.name).stem}.pdf",
                        mime="application/pdf",
                    )
        with coly:
            if mode == "Visual":
                st.caption("Creates a single PDF where each page shows A on the left and B on the right.")
            else:
                st.caption("Same merge, but with translucent rectangles highlighting changed words.")


# --- Page routing ---
st.title(f"AI‑Driven PDF Comparison · {page}")
if page == "Basic":
    st.caption("Quick diffs for text, tables, and images using pHash")
    _compare_flow(use_pro=False)
else:
    st.caption("Visual page review, text‑diff highlights, and merged side‑by‑side export")
    _side_by_side_flow()
