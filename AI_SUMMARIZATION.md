# AI Summarization Feature

## Overview
The PDF Compare AI Tool now includes AI-powered summarization using Google's Gemini 2.0 Flash model. This feature generates professional, structured comparison summaries of product specification PDFs.

## Setup

### 1. Install Dependencies
```bash
pip install google-generativeai reportlab
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### 2. Get Google API Key
1. Visit https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Create a new API key
4. Copy the API key

### 3. Set Environment Variable

**Windows (PowerShell):**
```powershell
$env:GOOGLE_API_KEY="your_api_key_here"
```

**Windows (Command Prompt):**
```cmd
set GOOGLE_API_KEY=your_api_key_here
```

**Linux/Mac:**
```bash
export GOOGLE_API_KEY=your_api_key_here
```

**Or create a `.env` file:**
```env
GOOGLE_API_KEY=your_api_key_here
```

## Usage

### Using Streamlit Web App

1. Run the Streamlit app:
```bash
streamlit run src/app/streamlit_app.py
```

2. Navigate to the **Basic** mode in the sidebar

3. Upload two PDF files (PDF A and PDF B)

4. Click the **🤖 AI Summarize** button

5. Wait for Gemini to generate the summary

6. View the structured comparison summary

7. Download the summary as Markdown (.md) or PDF (.pdf) file

### Using Python API

```python
from pdf_compare_solution import generate_ai_summary
import os

# Set your API key
os.environ['GOOGLE_API_KEY'] = 'your_api_key_here'

# Generate summary
summary = generate_ai_summary(
    pdf_a_path='path/to/pdf_a.pdf',
    pdf_b_path='path/to/pdf_b.pdf'
)

print(summary)
```

## Summary Structure

The AI generates a highly structured comparison that includes:

### 1. Document Overview
- Brand
- Product Code
- Description
- Barcode
- Commodity Code
- Country of Origin
- Document template/source

### 2. Key Functional & Feature Differences
- Design comparisons
- Material differences
- Performance features
- Displayed in table format with bullet summaries

### 3. Dimensional & Packaging Comparison
- Dimensions (Width, Height, Depth)
- Weight
- Packaging quantities
- Plastic/Cardboard usage
- Change indicators (Increase/Decrease/Equal)

### 4. Specification Summary Table
- Key differences by theme
- Business insights

### 5. Executive Insight
- 3-5 lines explaining real-world business impact
- Professional, technical, business-oriented tone

## Features

✅ **Intelligent Extraction**: Automatically extracts all text from both PDFs
✅ **Structured Output**: Consistent, professional formatting
✅ **Engineering Focus**: Highlights technical and functional differences
✅ **Business Context**: Provides executive-level insights
✅ **No Hallucination**: Only extracts actual content from PDFs
✅ **Multiple Formats**: Download summaries as Markdown or beautifully formatted PDF files

## Technical Details

- **Model**: Gemini 2.0 Flash (gemini-2.0-flash-exp)
- **Provider**: Google Generative AI
- **Input**: Full text extraction from both PDFs
- **Output Format**: Structured Markdown
- **Processing Time**: Typically 10-30 seconds depending on PDF size

## Troubleshooting

### "Google API key not found" Error
- Make sure you've set the `GOOGLE_API_KEY` environment variable
- Restart your terminal/IDE after setting the variable
- Verify the key is correct

### "google-generativeai package not installed" Error
- Install the package: `pip install google-generativeai`
- Ensure you're using the correct Python environment

### Summary quality issues
- Ensure PDFs contain actual text (not just scanned images)
- Check that PDFs are product specification documents
- The AI works best with structured technical datasheets

## Limitations

- Requires internet connection to access Gemini API
- API key required (free tier available)
- Works best with text-based PDFs (not scanned images)
- Optimized for product specification and datasheet PDFs
- Subject to Google API rate limits

## Cost

Google Gemini API offers a free tier with generous limits. Check current pricing at:
https://ai.google.dev/pricing

## Privacy

PDF content is sent to Google's Gemini API for processing. Do not use this feature with confidential or sensitive documents unless you have appropriate agreements with Google.
