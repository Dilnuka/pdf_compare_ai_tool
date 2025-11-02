# PDF Comparison Tool

Compare two PDFs and generate clear reports for text, table, and image differences. Optional AI mode produces an executive summary using Google Gemini. A Streamlit app is included for a friendly UI.

## Features
- Text diffs with context
- Table structure and cell diffs
- Image matching via perceptual hashing (pHash)
- AI summary (Gemini) with a structured, business-ready output
- Side‑by‑side visual comparison PDF (merge pages horizontally)
- Streamlit web app

## Installation

1) Create and activate a virtual environment
- Windows (PowerShell)
  - python -m venv venv
  - venv\Scripts\Activate.ps1

2) Install dependencies
- pip install -r requirements.txt

3) Optional: set your Gemini API key for AI summary
- PowerShell (current session):
  - $env:GOOGLE_API_KEY="your_key_here"

## Command‑line usage

Default: detailed HTML report
- python src/pdf_compare_solution.py PDF_A.pdf PDF_B.pdf --out report.html

AI summary (requires GOOGLE_API_KEY)
- python src/pdf_compare_solution.py PDF_A.pdf PDF_B.pdf --ai-summary --out summary.md

Side‑by‑side visual comparison
- python src/pdf_compare_solution.py PDF_A.pdf PDF_B.pdf --side-by-side --out merged.pdf
- optional: add --highlight to overlay text differences

## Streamlit app

Run the web UI:
- streamlit run src/app/streamlit_app.py

## Notes
- AI summary uses the prompt in prompt.md if present; otherwise a built‑in prompt is used.
- The side‑by‑side merge is provided by pdf_compare.visual.

## Repository layout
- src/pdf_compare_solution.py — CLI entry point (detailed, AI summary, side-by-side)
- src/app/streamlit_app.py — Streamlit UI
- src/utils/ — extraction, comparison, and PDF report generation
- src/pdf_compare/ — baseline and visual helpers
- assets/ — sample inputs/outputs (if any)
- tests/ — minimal tests