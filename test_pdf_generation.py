"""
Test script for PDF generation from markdown summary.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.pdf_generator import markdown_to_pdf

# Sample markdown text (similar to what Gemini would generate)
sample_markdown = """
# ✅ Automated Comparison Summary — Product Specification Docs

## **Document Overview**

| Field | Product A | Product B |
|-------|-----------|-----------|
| Brand | Acme Corporation | Acme Corporation |
| Product Code | AC-1234-X | AC-1234-Y |
| Description | Heavy Duty Wrench | Extra Heavy Duty Wrench |
| Barcode | 123456789012 | 123456789013 |
| Country of Origin | Germany | Germany |

## **Key Functional & Feature Differences**

| Category | Product A | Product B |
|----------|-----------|-----------|
| Material | Carbon Steel | Alloy Steel |
| Torque Rating | 100 Nm | 150 Nm |
| Handle Type | Rubber Grip | Ergonomic Soft Grip |
| Weight Class | Standard | Heavy Duty |

**Key Differences:**
- Product B features upgraded alloy steel construction for enhanced durability
- 50% increase in torque capacity (100 Nm → 150 Nm)
- Improved ergonomic handle design for better grip and comfort
- Heavier build quality suitable for industrial applications

## **Dimensional & Packaging Comparison**

| Attribute | Product A | Product B | Change |
|-----------|-----------|-----------|---------|
| Length | 250 mm | 280 mm | Increase |
| Width | 45 mm | 50 mm | Increase |
| Height | 20 mm | 22 mm | Increase |
| Weight | 450 g | 620 g | Increase |
| Package Quantity | 10 units | 5 units | Decrease |

**Summary:**
- Product B is 12% longer and 38% heavier than Product A
- Larger dimensions reflect heavy-duty construction
- Reduced package quantity due to increased individual unit size
- Both products use recyclable cardboard packaging

## **Specification Summary Table**

| Theme | Insight |
|-------|---------|
| Strength | Product B offers 50% higher torque rating |
| Durability | Alloy steel vs carbon steel construction |
| Ergonomics | Enhanced grip design in Product B |
| Weight | 38% heavier for industrial use |
| Packaging | Reduced quantity per box due to size |

## ✅ **AI-Style Executive Insight**

Product B represents a significant upgrade over Product A, targeting industrial and heavy-duty applications. The shift from carbon steel to alloy steel, combined with a 50% increase in torque capacity, positions Product B as a premium offering for professional use. While the increased weight (38% heavier) may reduce portability, it enhances structural integrity and durability for demanding tasks. The ergonomic handle improvement addresses user comfort during extended use. Organizations requiring robust tools for high-torque applications should consider Product B, while Product A remains suitable for standard maintenance tasks.
"""

if __name__ == "__main__":
    print("Generating PDF from sample markdown...")
    
    try:
        pdf_bytes = markdown_to_pdf(
            sample_markdown,
            title="Test PDF Comparison Summary"
        )
        
        # Save to file
        output_file = "test_summary_output.pdf"
        with open(output_file, 'wb') as f:
            f.write(pdf_bytes)
        
        print(f"✅ PDF generated successfully: {output_file}")
        print(f"   File size: {len(pdf_bytes)} bytes")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
