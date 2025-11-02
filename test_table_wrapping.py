"""
Test table wrapping in PDF generation.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
src_path = ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from utils.pdf_generator import markdown_to_pdf

# Test markdown with the tables from the images
test_markdown = """
# ✅ Automated Comparison Summary — Product Specification Docs

## Document Overview

| Field | Product A | Product B |
|---|---|---|
| Brand | CK | CK |
| Product Code | T0083 6 | T4343M 17 |
| Description | C.K Engineers File Round 150mm 2nd Cut | Combination Spanner 17mm |
| Barcode | 5013969390704 | 5013969550603 |
| Commodity Code | 8203100000 | 8204110000 |
| Country of Origin | PL | TW |
| Document Template / Source | cki.skoocloud.com | cki.skoocloud.com |

## Feature & Function Comparison

| Category | Product A | Product B |
|---|---|---|
| Tool Type | File | Combination Spanner |
| Primary Function | Material Removal | Fastening |
| Material | Special file steel | Drop forged chrome vanadium steel |
| Key Features | Precision cut and hardened, ergonomic soft grip handle, solid inner core, tapered | Hardened & tempered, heavy duty chrome plated, 12° offset bi-hexagonal ring |
| Design Focus | Performance and durability, comfort and control, safety | Strength & durability, corrosion resistance |

## Packaging — Weights & Measures

| Attribute | Product Only | Primary Pack | Secondary Pack | Transit Pack |
|---|---|---|---|---|
| Quantity | 1 | 1 | 3 (Product A) / 10 (Product B) | 90 (Product A) / 150 (Product B) |
| Width | 3 mm (Product A) / 37 mm (Product B) | 27 mm (Product A) / 37 mm (Product B) | 100 mm (Product A) / 80 mm (Product B) | 450 mm (Product A) / 450 mm (Product B) |
| Depth | 3 mm | 15 mm | 18 mm (Product A) / 240 mm (Product B) | 350 mm |
| Height | 150 mm (Product A) / 210 mm (Product B) | 260 mm (Product A) / 210 mm (Product B) | 290 mm (Product A) / 60 mm (Product B) | 350 mm (Product A) / 350 mm (Product B) |
| Weight | 40 g (Product A) / 126 g (Product B) | 54 g (Product A) / 126 g (Product B) | 168 g (Product A) / 1294 g (Product B) | 5.8 kg (Product A) / 20 kg (Product B) |

## Key Insights

• Product A is a precision file tool designed for material removal with ergonomic features
• Product B is a combination spanner for fastening applications with corrosion resistance
• Material selection differs significantly: special file steel vs chrome vanadium steel
• Product A originates from Poland (PL) while Product B is manufactured in Taiwan (TW)
• Packaging quantities vary substantially: Product B has higher bulk packaging (150 vs 90 transit pack)
• Weight difference: Product A is lighter (40g) compared to Product B (126g) at product level
• Both products maintain professional-grade quality standards for their respective applications
• Supply chain diversity with different country origins may offer procurement flexibility

## Executive Summary

These products represent distinct tool categories with different applications. Product A (file) focuses on precision material removal with ergonomic design from Poland, while Product B (spanner) emphasizes fastening strength and corrosion resistance from Taiwan. The weight and packaging differences reflect their intended use cases, with the spanner being more suitable for bulk procurement. Both products demonstrate professional-grade quality suitable for industrial and commercial applications.
"""

# Generate PDF
print("Generating test PDF with wrapped table cells...")
pdf_bytes = markdown_to_pdf(test_markdown, title="Table Wrapping Test Report")

# Save to file
output_path = ROOT / "test_table_output.pdf"
output_path.write_bytes(pdf_bytes)

print(f"✅ PDF generated successfully: {output_path}")
print(f"   File size: {len(pdf_bytes):,} bytes")
print("\nPlease open the PDF and verify:")
print("  1. Table cells with long text wrap properly within their cells")
print("  2. No text overflow or cutting off")
print("  3. Rows maintain proper height for multi-line content")
print("  4. Tables are properly aligned and readable")
