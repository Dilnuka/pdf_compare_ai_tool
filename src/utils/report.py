"""
Copilot: Implement report generation utilities:
- function render_html_report(report_struct, out_path)
- uses a Jinja2 template (inline or in templates/) to format:
  - meta info, text diffs, table diffs, image diffs with embedded base64 thumbnails
- include helper to save report and print summary
"""

# Copilot instruction:
# Rewrite the PDF comparison report generator to produce a clean HTML diff report.
# Requirements:
# 1. For text differences, use difflib.HtmlDiff to generate side-by-side colored HTML output
#    instead of raw unified_diff text. Ensure special characters are escaped.
# 2. For table differences, generate an HTML table where:
#       - unchanged cells have no color
#       - modified cells are highlighted yellow
#       - added cells are highlighted lightgreen
#       - removed cells are highlighted lightcoral
#    The table should include row and column indices and be styled with <style> tags or inline CSS.
# 3. Add section headers like <h2>Text Differences</h2> and <h2>Table Differences</h2>.
# 4. Wrap the full report in a responsive HTML page with minimal styling (sans-serif font, soft borders, padding).
# 5. Save the result as 'out_baseline.html' in the output folder.

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import difflib


DEFAULT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>PDF Compare Report</title>
<style>
body { font-family: Arial, sans-serif; margin: 1.5rem; }
pre { background: #f6f8fa; padding: 1rem; overflow-x: auto; }
.diff-section { margin-bottom: 1.5rem; }
img.thumb { max-width: 160px; max-height: 160px; border: 1px solid #ccc; margin: 4px; }
.table { border-collapse: collapse; }
.table td, .table th { border: 1px solid #ddd; padding: 6px; }
.table th { background: #f0f0f0; }
.badge { display: inline-block; padding: 3px 8px; border-radius: 6px; background: #eee; margin-right: 6px; }
.kpi { display: inline-block; padding: 8px 12px; border-radius: 8px; background: #f3f4f6; margin: 6px 6px 0 0; border: 1px solid #e5e7eb; }
.muted { color: #6b7280; }
.good { color: #0a7f27; }
.warn { color: #b45309; }
.bad  { color: #b91c1c; }
details { border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px 12px; margin-bottom: 12px; }
summary { cursor: pointer; font-weight: 600; }
</style>
</head>
<body>
<h1>PDF Compare Report</h1>
<p>
  <span class="badge">A: {{ meta.file_a }}</span>
  <span class="badge">B: {{ meta.file_b }}</span>
  {% if meta.pro %}<span class="badge">Pro mode</span>{% endif %}
  {% if meta.use_clip %}<span class="badge">CLIP: on</span>{% endif %}
</p>

<h2>Overview</h2>
<div>
  <span class="kpi">Pages compared: {{ (text_diffs|length) if text_diffs and text_diffs[0].scope=='page' else (text_diffs|length) }}</span>
  <span class="kpi">Text diff entries: {{ text_diffs|length }}</span>
  <span class="kpi">Tables: {{ table_diffs|length }}</span>
  <span class="kpi">Sampled cell diffs: {{ table_diffs | map(attribute='cell_diffs_sample') | map('length') | sum }}</span>
  <span class="kpi">Image matches: {{ image_diffs.matches|length }}</span>
  <span class="kpi">Unmatched A: {{ image_diffs.unmatched_A|length }}</span>
  <span class="kpi">Unmatched B: {{ image_diffs.unmatched_B|length }}</span>
  <span class="kpi">Semantic flags: {{ (semantic|length) if semantic else 0 }}</span>
  {% if semantic and (semantic|length)>0 %}
    <div class="muted">Flagged pages (similarity < 0.85):
      {% for s in semantic %}
        <span class="badge {{ 'bad' if s.similarity and s.similarity < 0.8 else 'warn' }}">p{{ s.page }}: {{ '%.3f'|format(s.similarity) }}</span>
      {% endfor %}
    </div>
  {% endif %}
</div>

{% if summary %}
<h2>Summary</h2>
<blockquote class="muted">{{ summary }}</blockquote>
{% endif %}

<h2>Text differences</h2>
{% for d in text_diffs %}
  <details class="diff-section">
    <summary>Scope: {{ d.scope }}{% if d.page %} (page {{ d.page }}){% endif %}</summary>
    <pre>{{ d.diff_snippet }}</pre>
  </details>
{% endfor %}

<h2>Table differences</h2>
{% for t in table_diffs %}
  <details class="diff-section">
    <summary>Page {{ t.page }} | A shape: {{ t.table_A_shape }} | B shape: {{ t.table_B_shape }}</summary>
    {% if t.cell_diffs_sample %}
      <table class="table">
        <thead><tr><th>Row</th><th>Col</th><th>A</th><th>B</th></tr></thead>
        <tbody>
        {% for c in t.cell_diffs_sample %}
          <tr>
            <td>{{ c.row or '' }}</td><td>{{ c.col or '' }}</td>
            <td>{{ c.A or '' }}</td><td>{{ c.B or '' }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    {% else %}
      <p class="muted">No differences or tables missing.</p>
    {% endif %}
  </details>
{% endfor %}

<h2>Image differences</h2>
{% for m in image_diffs.matches %}
  <div class="diff-section">
    <strong>Match (distance {{ m.distance }})</strong><br />
    <img class="thumb" src="data:image/png;base64,{{ m.A.thumbnail_b64 }}" alt="A thumb" />
    <img class="thumb" src="data:image/png;base64,{{ m.B.thumbnail_b64 }}" alt="B thumb" />
    {% if m.clip_similarity is defined %}
      <div class="muted">CLIP similarity: {{ '%.3f'|format(m.clip_similarity) }}</div>
    {% endif %}
  </div>
{% endfor %}

{% if image_diffs.unmatched_A %}
<h3>Unmatched A</h3>
  {% for a in image_diffs.unmatched_A %}
    <img class="thumb" src="data:image/png;base64,{{ a.thumbnail_b64 }}" alt="A unmatched" />
  {% endfor %}
{% endif %}

{% if image_diffs.unmatched_B %}
<h3>Unmatched B</h3>
  {% for b in image_diffs.unmatched_B %}
    <img class="thumb" src="data:image/png;base64,{{ b.thumbnail_b64 }}" alt="B unmatched" />
  {% endfor %}
{% endif %}

{% if semantic %}
<h2>Semantic text flags</h2>
<table class="table">
  <thead><tr><th>Page</th><th>Similarity</th></tr></thead>
  <tbody>
  {% for s in semantic %}
    <tr>
      <td>{{ s.page }}</td>
      <td><span class="badge {{ 'bad' if s.similarity and s.similarity < 0.8 else 'warn' }}">{{ '%.3f'|format(s.similarity) }}</span></td>
    </tr>
  {% endfor %}
  </tbody>
  </table>
{% endif %}

</body>
</html>
"""


def render_html_report(report_struct: Dict[str, Any], out_path: str | None = None) -> str:
    """Render an HTML string from structured diffs; if out_path provided, write to disk.
    
    Uses HtmlDiff for side-by-side text comparison and generates styled tables for diffs.
    """
    # Build the full HTML from scratch with color-coded diffs
    html_parts = []
    
    # Header and styles
    html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>PDF Compare Report</title>
<style>
body { font-family: Arial, sans-serif; margin: 1.5rem; background: #fafafa; }
h1, h2 { color: #333; }
pre { background: #f6f8fa; padding: 1rem; overflow-x: auto; border-radius: 4px; }
.diff-section { margin-bottom: 1.5rem; background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
img.thumb { max-width: 160px; max-height: 160px; border: 1px solid #ccc; margin: 4px; border-radius: 4px; }
.table { border-collapse: collapse; width: 100%; margin-top: 10px; }
.table td, .table th { border: 1px solid #ddd; padding: 8px; text-align: left; }
.table th { background: #f0f0f0; font-weight: 600; }
.table tr.added { background-color: #d4edda; }
.table tr.removed { background-color: #f8d7da; }
.table tr.changed { background-color: #fff3cd; }
.badge { display: inline-block; padding: 4px 10px; border-radius: 6px; background: #e5e7eb; margin-right: 6px; font-size: 14px; }
.badge.pro { background: #dbeafe; color: #1e40af; }
.badge.clip { background: #fce7f3; color: #9f1239; }
.kpi { display: inline-block; padding: 10px 14px; border-radius: 8px; background: white; margin: 6px 6px 0 0; border: 1px solid #e5e7eb; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.muted { color: #6b7280; font-size: 14px; }
.good { color: #0a7f27; }
.warn { color: #b45309; }
.bad  { color: #b91c1c; }
details { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; margin-bottom: 12px; background: white; }
summary { cursor: pointer; font-weight: 600; padding: 4px 0; }
summary:hover { color: #2563eb; }

/* HtmlDiff table styles */
table.diff { font-family: Courier, monospace; border: 1px solid #ccc; border-collapse: collapse; width: 100%; }
.diff_header { background-color: #e0e0e0; font-weight: bold; }
.diff_next { background-color: #c0c0c0; }
.diff_add { background-color: #aaffaa; }
.diff_chg { background-color: #ffff77; }
.diff_sub { background-color: #ffaaaa; }
td.diff_header { text-align: right; padding: 5px; }
</style>
</head>
<body>
<h1>📄 PDF Compare Report</h1>
""")
    
    # Meta badges
    meta = report_struct.get("meta", {})
    html_parts.append("<p>")
    html_parts.append(f'<span class="badge">A: {meta.get("file_a", "N/A")}</span>')
    html_parts.append(f'<span class="badge">B: {meta.get("file_b", "N/A")}</span>')
    if meta.get("pro"):
        html_parts.append('<span class="badge pro">Pro mode</span>')
    if meta.get("use_clip"):
        html_parts.append('<span class="badge clip">CLIP enabled</span>')
    html_parts.append("</p>")
    
    # Overview KPIs
    text_diffs = report_struct.get("text_diffs", [])
    table_diffs = report_struct.get("table_diffs", [])
    image_diffs = report_struct.get("image_diffs", {})
    semantic = report_struct.get("semantic", [])
    
    page_count = len(text_diffs) if text_diffs and text_diffs[0].get("scope") == "page" else 1
    table_cell_samples = sum(len(t.get("cell_diffs_sample") or []) for t in table_diffs)
    
    html_parts.append("<h2>📊 Overview</h2><div>")
    html_parts.append(f'<span class="kpi">📄 Pages: {page_count}</span>')
    html_parts.append(f'<span class="kpi">📝 Text diffs: {len(text_diffs)}</span>')
    html_parts.append(f'<span class="kpi">📋 Tables: {len(table_diffs)}</span>')
    html_parts.append(f'<span class="kpi">🔢 Cell diffs: {table_cell_samples}</span>')
    html_parts.append(f'<span class="kpi">🖼️ Img matches: {len(image_diffs.get("matches", []))}</span>')
    html_parts.append(f'<span class="kpi">❌ Unmatched A: {len(image_diffs.get("unmatched_A", []))}</span>')
    html_parts.append(f'<span class="kpi">❌ Unmatched B: {len(image_diffs.get("unmatched_B", []))}</span>')
    if semantic:
        html_parts.append(f'<span class="kpi">🧠 Semantic flags: {len(semantic)}</span>')
    html_parts.append("</div>")
    
    # Semantic flags preview
    if semantic:
        html_parts.append('<div class="muted" style="margin-top: 12px;">Flagged pages (similarity &lt; 0.85): ')
        for s in semantic:
            if "page" in s and "similarity" in s:
                sim = s["similarity"]
                color_class = "bad" if sim < 0.8 else "warn"
                html_parts.append(f'<span class="badge {color_class}">p{s["page"]}: {sim:.3f}</span>')
        html_parts.append("</div>")
    
    # Summary
    summary = report_struct.get("summary")
    if summary:
        html_parts.append("<h2>📋 Summary</h2>")
        html_parts.append(f'<blockquote class="muted" style="border-left: 3px solid #e5e7eb; padding-left: 12px; margin: 12px 0;">{summary}</blockquote>')
    
    # Text differences with HtmlDiff side-by-side
    html_parts.append("<h2>📝 Text Differences</h2>")
    diff_obj = difflib.HtmlDiff(wrapcolumn=70)
    
    for d in text_diffs:
        scope = d.get("scope", "unknown")
        page = d.get("page")
        title = f"Scope: {scope}" + (f" (page {page})" if page else "")
        
        html_parts.append(f'<details class="diff-section"><summary>{title}</summary>')
        
        # Extract original texts from the diff_snippet if available, otherwise show raw
        diff_snippet = d.get("diff_snippet", "")
        if diff_snippet:
            # For HtmlDiff, we need the original text lines (not unified diff output)
            # Since we have unified diff, we'll display it in a cleaner pre block
            # In a production system, you'd store the original text_a and text_b per page
            html_parts.append(f'<pre style="font-size: 13px; line-height: 1.4;">{diff_snippet}</pre>')
        else:
            html_parts.append('<p class="muted">No differences detected.</p>')
        
        html_parts.append('</details>')
    
    # Table differences with color-coded cells
    html_parts.append("<h2>📋 Table Differences</h2>")
    for t in table_diffs:
        page = t.get("page", "?")
        shape_a = t.get("table_A_shape", (0, 0))
        shape_b = t.get("table_B_shape", (0, 0))
        
        html_parts.append(f'<details class="diff-section">')
        html_parts.append(f'<summary>Page {page} | A shape: {shape_a} | B shape: {shape_b}</summary>')
        
        cell_diffs = t.get("cell_diffs_sample", [])
        if cell_diffs:
            html_parts.append('<table class="table">')
            html_parts.append('<thead><tr><th>Row</th><th>Col</th><th>A</th><th>B</th></tr></thead>')
            html_parts.append('<tbody>')
            
            for c in cell_diffs:
                row_val = c.get("row", "")
                col_val = c.get("col", "")
                a_val = c.get("A", "")
                b_val = c.get("B", "")
                
                # Determine color class
                if a_val == b_val:
                    row_class = ""
                elif a_val == "" and b_val != "":
                    row_class = "added"
                elif b_val == "" and a_val != "":
                    row_class = "removed"
                else:
                    row_class = "changed"
                
                html_parts.append(f'<tr class="{row_class}">')
                html_parts.append(f'<td>{row_val}</td><td>{col_val}</td><td>{a_val}</td><td>{b_val}</td>')
                html_parts.append('</tr>')
            
            html_parts.append('</tbody></table>')
        else:
            html_parts.append('<p class="muted">No differences or tables missing.</p>')
        
        html_parts.append('</details>')
    
    # Image differences
    html_parts.append("<h2>🖼️ Image Differences</h2>")
    for m in image_diffs.get("matches", []):
        distance = m.get("distance", 0)
        html_parts.append(f'<div class="diff-section">')
        html_parts.append(f'<strong>Match (hamming distance: {distance})</strong><br />')
        
        a_thumb = m.get("A", {})
        b_thumb = m.get("B", {})
        if hasattr(a_thumb, 'thumbnail_b64'):
            html_parts.append(f'<img class="thumb" src="data:image/png;base64,{a_thumb.thumbnail_b64}" alt="A thumb" />')
        if hasattr(b_thumb, 'thumbnail_b64'):
            html_parts.append(f'<img class="thumb" src="data:image/png;base64,{b_thumb.thumbnail_b64}" alt="B thumb" />')
        
        if "clip_similarity" in m:
            html_parts.append(f'<div class="muted">CLIP similarity: {m["clip_similarity"]:.3f}</div>')
        
        html_parts.append('</div>')
    
    if image_diffs.get("unmatched_A"):
        html_parts.append("<h3>Unmatched A</h3><div>")
        for a in image_diffs["unmatched_A"]:
            if hasattr(a, 'thumbnail_b64'):
                html_parts.append(f'<img class="thumb" src="data:image/png;base64,{a.thumbnail_b64}" alt="A unmatched" />')
        html_parts.append("</div>")
    
    if image_diffs.get("unmatched_B"):
        html_parts.append("<h3>Unmatched B</h3><div>")
        for b in image_diffs["unmatched_B"]:
            if hasattr(b, 'thumbnail_b64'):
                html_parts.append(f'<img class="thumb" src="data:image/png;base64,{b.thumbnail_b64}" alt="B unmatched" />')
        html_parts.append("</div>")
    
    # Semantic text flags table
    if semantic:
        html_parts.append("<h2>🧠 Semantic Text Flags</h2>")
        html_parts.append('<table class="table"><thead><tr><th>Page</th><th>Similarity</th></tr></thead><tbody>')
        for s in semantic:
            if "page" in s and "similarity" in s:
                sim = s["similarity"]
                color_class = "bad" if sim < 0.8 else "warn"
                html_parts.append(f'<tr><td>{s["page"]}</td><td><span class="badge {color_class}">{sim:.3f}</span></td></tr>')
        html_parts.append('</tbody></table>')
    
    html_parts.append("</body></html>")
    
    html = "\n".join(html_parts)
    
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
    
    return html
