"""Streamlit web app for PDF comparison."""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path

# Fix for Streamlit+PyTorch watcher conflict
os.environ.setdefault("STREAMLIT_WATCHER_TYPE", "poll")

import sys
import types

# Prevent torch.classes module errors
if 'torch.classes' not in sys.modules:
    dummy_mod = types.ModuleType('torch.classes')
    class _DummyPath:
        _path: list = []
    dummy_mod.__path__ = _DummyPath()
    sys.modules['torch.classes'] = dummy_mod

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
    text_diff_rects,
    text_diff_stats,
)  # type: ignore
from utils.env import ensure_google_api_key  # type: ignore

st.set_page_config(page_title="PDF Compare", page_icon="🧾", layout="wide")

# Session state
if "reports" not in st.session_state:
    st.session_state.reports = []

# Sidebar
st.sidebar.title("🧾 PDF Compare")

size_preset = st.sidebar.selectbox(
    "Upload area size",
    options=["Compact", "Comfortable", "Spacious"],
    index=1
)
_HEIGHT_MAP = {"Compact": "28vh", "Comfortable": "40vh", "Spacious": "60vh"}
dz_height = _HEIGHT_MAP.get(size_preset, "40vh")

page = st.sidebar.radio("Navigation", ["Basic", "Side‑by‑Side"])

# Custom CSS for upload dropzones
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
    # Per-report actions (download + delete)
    for i, rep in enumerate(st.session_state.reports[:5]):
        cdl, cdel = st.sidebar.columns([0.78, 0.22])
        with cdl:
            st.download_button(
                key=f"sdl_{i}", label=rep["title"], data=rep["html"], file_name=rep["title"], mime="text/html",
                use_container_width=True,
            )
        with cdel:
            if st.button("🗑️", key=f"del_rep_{i}", help="Delete this report", use_container_width=True):
                try:
                    del st.session_state.reports[i]
                except Exception:
                    pass
                st.rerun()

    # Bulk action
    st.sidebar.markdown("")
    if st.sidebar.button("Clear all reports", type="secondary"):
        st.session_state.reports = []
        st.rerun()


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

    # Centered Compare and Summarize button row
    spacer_left, center_col, spacer_right = st.columns([1, 0.6, 1])
    with center_col:
        compare_btn = st.button(
            "Compare",
            type="primary",
            use_container_width=True,
            key=("cmp_pro" if use_pro else "cmp_basic"),
        )
        
        # Add Summarize button only for basic mode
        if not use_pro:
            summarize_btn = st.button(
                "🤖 AI Summarize",
                type="secondary",
                use_container_width=True,
                key="summarize_basic",
            )
        else:
            summarize_btn = False

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
    
    # (Removed) AI pages options: always process full documents now

    # Handle AI Summarize button (only for basic mode)
    if summarize_btn:
        if not file_a or not file_b:
            st.warning("Please upload both PDFs.")
            st.stop()
        
        # Check for API key (auto-load from .env/.env.local/.env.example if needed)
        api_key = ensure_google_api_key()
        if not api_key:
            st.error("❌ Google API Key not found. Please set the GOOGLE_API_KEY environment variable.")
            st.info("💡 You can get a free API key from https://makersuite.google.com/app/apikey")
            st.stop()
        
        tmp_dir = Path(".tmp_uploads")
        tmp_dir.mkdir(exist_ok=True)
        path_a = tmp_dir / (file_a.name or "a.pdf")
        path_b = tmp_dir / (file_b.name or "b.pdf")
        
        # Write files if not already written
        if not path_a.exists():
            path_a.write_bytes(file_a.read())
        if not path_b.exists():
            file_b.seek(0)  # Reset file pointer
            path_b.write_bytes(file_b.read())
        
        with st.spinner("🤖 Generating AI summary using Gemini… This may take a moment."):
            # Reload module to avoid stale signatures under Streamlit's runner
            import importlib  # type: ignore
            import pdf_compare_solution as pcs  # type: ignore
            try:
                importlib.reload(pcs)
            except Exception:
                pass
            fn = getattr(pcs, "generate_ai_summary")
            try:
                import inspect  # type: ignore
                params = inspect.signature(fn).parameters
                if "page_limit" in params:
                    # Do not pass page_limit (use default = no limit)
                    summary = fn(str(path_a), str(path_b), api_key)
                else:
                    # Backward-compatible call if older function signature is loaded
                    summary = fn(str(path_a), str(path_b), api_key)
            except Exception as e:
                summary = f"Error generating AI summary: {e}"
        
        st.success("✅ AI Summary generated successfully!")

        # Prepare and persist results so download doesn't clear the UI
        try:
            from utils.pdf_generator import markdown_to_pdf  # type: ignore
            pdf_bytes = markdown_to_pdf(
                summary,
                title=f"Comparison: {Path(file_a.name).stem} vs {Path(file_b.name).stem}"
            )
        except ImportError:
            pdf_bytes = None
            st.warning("⚠️ PDF generation requires 'reportlab'. Install with: pip install reportlab")
        except Exception as e:
            pdf_bytes = None
            st.error(f"❌ Error generating PDF: {e}")

        st.session_state.ai_summary = {
            "text": summary,
            "pdf": pdf_bytes,
            "fname": f"summary_{Path(file_a.name).stem}_vs_{Path(file_b.name).stem}.pdf",
        }

    # Persistent render of last AI summary (if available)
    if not use_pro and st.session_state.get("ai_summary"):
        data = st.session_state.ai_summary
        with st.expander("📊 AI Comparison Summary", expanded=True):
            if isinstance(data.get("text"), str) and data["text"].startswith("Error generating AI summary"):
                st.error(data["text"])
                st.info("Try reducing 'AI pages used' in AI Options or trying again later.")
            else:
                st.markdown(data.get("text", ""))

        if data.get("pdf"):
            st.download_button(
                label="📄 Download as PDF",
                data=data["pdf"],
                file_name=data.get("fname", "summary.pdf"),
                mime="application/pdf",
                use_container_width=True,
                key="dl_summary_pdf_persist",
            )


@st.cache_data(show_spinner=False)
def _render_png_bytes(pdf_bytes: bytes, page_index: int, zoom: float = 1.8) -> bytes:
    """Cache-friendly rendering of a PDF page to PNG bytes for Streamlit display."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        p = doc[page_index]
        pix = p.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")


def _render_zoom_controls(prefix: str = "") -> None:
    """Render a horizontal zoom control bar (Reset, −, %, +).

    The controls are laid out with equal visual spacing and operate on the
    shared st.session_state.zoom_level so both panes stay in sync.
    The prefix guarantees unique Streamlit widget keys for each pane.
    """
    # Layout: Reset | gap | − | gap | % | gap | +
    c1, g1, c2, g2, c3, g3, c4 = st.columns([2, 0.3, 1, 0.3, 1.2, 0.3, 1])

    with c1:
        if st.button("Reset to 100%", key=f"zoom_reset_{prefix}", use_container_width=True, type="secondary"):
            st.session_state.zoom_level = 1.0
            st.rerun()

    with c2:
        if st.button("−", key=f"zoom_out_{prefix}", use_container_width=True, type="secondary"):
            zoom_options = [0.5, 0.75, 1.0, 1.25, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0]
            current_idx = zoom_options.index(st.session_state.zoom_level) if st.session_state.zoom_level in zoom_options else 2
            if current_idx > 0:
                st.session_state.zoom_level = zoom_options[current_idx - 1]
                st.rerun()

    with c3:
        zoom_pct = int(st.session_state.zoom_level * 100)
        st.markdown(
            f'<div class="zoom-display-box" style="margin-top: 4px;">{zoom_pct}%</div>',
            unsafe_allow_html=True,
        )

    with c4:
        # Use fullwidth plus (U+FF0B) for reliable rendering across fonts
        if st.button("＋", key=f"zoom_in_{prefix}", use_container_width=True, type="secondary"):
            zoom_options = [0.5, 0.75, 1.0, 1.25, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0]
            current_idx = zoom_options.index(st.session_state.zoom_level) if st.session_state.zoom_level in zoom_options else 2
            if current_idx < len(zoom_options) - 1:
                st.session_state.zoom_level = zoom_options[current_idx + 1]
                st.rerun()


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
        
        # Compute total differences if in Compare Text mode
        if mode == "Compare Text":
            with st.spinner("Analyzing differences across all pages…"):
                total_text = 0
                total_numbers = 0
                total_images = 0
                page_stats = []
                
                for i in range(total):
                    stats = text_diff_stats(bytes_a, bytes_b, i)
                    page_stats.append(stats)
                    total_text += stats["text_changes"]
                    total_numbers += stats["number_changes"]
                    total_images += stats["image_changes"]
                
                total_all = total_text + total_numbers
                
                # Display summary with breakdown
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("� Text Changes", total_text)
                with col2:
                    st.metric("🔢 Number Changes", total_numbers)
                with col3:
                    st.metric("🖼️ Image Changes", total_images)
                with col4:
                    st.metric("📊 Total Words", total_all)
        
        st.caption(f"Showing {total} paired pages")
        if total > 1:
            pg = st.slider("Page", 1, total, 1, key="page_visual")
        else:
            pg = 1
        
        # Show per-page difference count in Compare Text mode
        if mode == "Compare Text" and 'page_stats' in locals():
            curr_stats = page_stats[pg - 1]
            parts = []
            if curr_stats["text_changes"] > 0:
                parts.append(f"{curr_stats['text_changes']} text")
            if curr_stats["number_changes"] > 0:
                parts.append(f"{curr_stats['number_changes']} numbers")
            if curr_stats["image_changes"] > 0:
                parts.append(f"{curr_stats['image_changes']} images")
            
            if parts:
                st.caption(f"🔍 Page {pg}: {', '.join(parts)} changed")
            else:
                st.caption(f"✅ Page {pg}: No differences detected")
        
        # Initialize zoom state
        if "zoom_level" not in st.session_state:
            st.session_state.zoom_level = 1.0
        
        # Add legend for Compare Text mode
        if mode == "Compare Text":
            st.info("💡 **Yellow boxes** outline text/number differences between the two PDFs")
        
        ca, cb = st.columns(2, gap="large")
        with st.spinner("Rendering page images…"):
            if mode == "Visual":
                img_a = _render_png_bytes(bytes_a, pg - 1, st.session_state.zoom_level)
                img_b = _render_png_bytes(bytes_b, pg - 1, st.session_state.zoom_level)
            else:
                img_a, img_b = render_page_pair_png_highlight(bytes_a, bytes_b, pg - 1, zoom=st.session_state.zoom_level, opacity=0.18)
        
        # Convert images to base64 for HTML display with scrolling
        import base64
        img_a_b64 = base64.b64encode(img_a).decode()
        img_b_b64 = base64.b64encode(img_b).decode()
        
        with ca:
            st.markdown(f"**A · Page {pg}**")
            st.markdown(
                f'''<div class="pdf-scroll-container">
                    <img src="data:image/png;base64,{img_a_b64}" style="display: block; max-width: none;">
                </div>''',
                unsafe_allow_html=True
            )
        with cb:
            st.markdown(f"**B · Page {pg}**")
            st.markdown(
                f'''<div class="pdf-scroll-container">
                    <img src="data:image/png;base64,{img_b_b64}" style="display: block; max-width: none;">
                </div>''',
                unsafe_allow_html=True
            )
        
        # Styles for scroll containers and zoom controls
        st.markdown(
            """
            <style>
            /* Scrollable PDF container */
            .pdf-scroll-container {
                width: 100%;
                height: 88vh; /* taller viewing area to reduce empty space */
                overflow: auto;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                background: #f9fafb;
                padding: 12px; /* slightly tighter padding for more room */
                scrollbar-gutter: stable both-edges; /* keep scrollbars beside content */
                box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
            }

            /* Keep things usable on short screens */
            @media (max-height: 800px) {
                .pdf-scroll-container { height: 77vh; }
            }
            
            /* Custom scrollbar styling */
            .pdf-scroll-container::-webkit-scrollbar {
                width: 12px;
                height: 12px;
            }
            
            .pdf-scroll-container::-webkit-scrollbar-track {
                background: #f1f5f9;
                border-radius: 6px;
            }
            
            .pdf-scroll-container::-webkit-scrollbar-thumb {
                background: #cbd5e1;
                border-radius: 6px;
                border: 2px solid #f1f5f9;
            }
            
            .pdf-scroll-container::-webkit-scrollbar-thumb:hover {
                background: #94a3b8;
            }
            
            .pdf-scroll-container::-webkit-scrollbar-corner {
                background: #f1f5f9;
            }
            
            /* Streamlit button styling overrides for zoom controls */
            div[data-testid="column"] button[kind="secondary"] {
                border-radius: 8px !important;
                border: 1.5px solid #d1d5db !important;
                background: white !important;
                color: #374151 !important;
                font-size: 20px !important;
                font-weight: 400 !important;
                padding: 8px !important;
                min-height: 38px !important;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
                transition: all 0.15s ease !important;
            }
            div[data-testid="column"] button[kind="secondary"]:hover {
                background: #f9fafb !important;
                border-color: #9ca3af !important;
                box-shadow: 0 2px 4px rgba(0,0,0,0.12) !important;
            }
            div[data-testid="column"] button[kind="secondary"]:active {
                transform: scale(0.97) !important;
            }
            .zoom-display-box {
                background: white;
                border: 1.5px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 20px;
                text-align: center;
                font-size: 15px;
                font-weight: 600;
                color: #1f2937;
                min-width: 80px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
                margin: 0 auto;
                display: inline-block;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        # Central zoom bar, well centered below both panes
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        left_sp, center_controls, right_sp = st.columns([1, 2, 1])
        with center_controls:
            _render_zoom_controls(prefix="center")


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
