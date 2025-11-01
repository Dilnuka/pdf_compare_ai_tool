"""
Utility to convert Markdown summary to PDF format.
"""

from __future__ import annotations

import io
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def markdown_to_pdf(markdown_text: str, title: str = "PDF Comparison Summary") -> bytes:
    """
    Convert markdown text to a formatted PDF.
    
    Args:
        markdown_text: The markdown content to convert
        title: Title for the PDF document
    
    Returns:
        PDF bytes that can be downloaded
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.colors import HexColor
        import re
    except ImportError:
        logger.error("reportlab package not installed. Install with: pip install reportlab")
        raise ImportError("reportlab package required for PDF generation. Install with: pip install reportlab")
    
    # Create a BytesIO buffer
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define custom styles
    styles = getSampleStyleSheet()
    
    # Custom title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Custom heading styles
    h1_style = ParagraphStyle(
        'CustomH1',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=HexColor('#2563eb'),
        spaceAfter=12,
        spaceBefore=16,
        fontName='Helvetica-Bold',
        borderPadding=5,
    )
    
    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=HexColor('#1e40af'),
        spaceAfter=10,
        spaceBefore=12,
        fontName='Helvetica-Bold',
    )
    
    h3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=HexColor('#374151'),
        spaceAfter=8,
        spaceBefore=10,
        fontName='Helvetica-Bold',
    )
    
    # Body text style
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=HexColor('#1f2937'),
        spaceAfter=6,
        alignment=TA_JUSTIFY,
        fontName='Helvetica',
    )
    
    # Bullet style
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=HexColor('#1f2937'),
        spaceAfter=4,
        leftIndent=20,
        fontName='Helvetica',
    )
    
    # Add metadata header
    date_str = datetime.now().strftime("%B %d, %Y")
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Generated on {date_str}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Parse markdown and convert to PDF elements
    lines = markdown_text.split('\n')
    current_table_data = []
    in_table = False
    
    for line in lines:
        line = line.strip()
        
        if not line:
            if in_table and current_table_data:
                # Render the table
                table = Table(current_table_data, repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3b82f6')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('TOPPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, HexColor('#e5e7eb')),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f9fafb')]),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 0.2*inch))
                current_table_data = []
                in_table = False
            else:
                elements.append(Spacer(1, 0.1*inch))
            continue
        
        # Headers
        if line.startswith('# '):
            text = line[2:].replace('✅', '').strip()
            elements.append(Paragraph(text, h1_style))
        elif line.startswith('## '):
            text = line[3:].replace('**', '').replace('✅', '').strip()
            elements.append(Paragraph(text, h2_style))
        elif line.startswith('### '):
            text = line[4:].replace('**', '').strip()
            elements.append(Paragraph(text, h3_style))
        
        # Tables
        elif '|' in line and not line.startswith('|--'):
            in_table = True
            # Parse table row
            cells = [cell.strip() for cell in line.split('|')]
            cells = [c for c in cells if c]  # Remove empty cells
            if cells:
                current_table_data.append(cells)
        
        # Bullets (support '-', '*', and '•')
        elif line.startswith('- ') or line.startswith('* ') or line.startswith('• '):
            text = line[2:] if not line.startswith('• ') else line[1:].strip()
            # Properly handle bold markdown
            text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
            text = text.replace('✅', '')
            elements.append(Paragraph(f"• {text}", bullet_style))
        
        # Regular paragraph
        else:
            if not in_table:
                # Clean up markdown formatting with proper regex
                text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', line)
                text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
                text = text.replace('✅', '')
                if text:
                    elements.append(Paragraph(text, body_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
