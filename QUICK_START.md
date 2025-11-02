# Quick Start Guide - AI Summarization Feature

## Step-by-Step Setup

### 1. Install the Package
```bash
pip install google-generativeai
```

### 2. Get Your API Key
1. Go to https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated key

### 3. Set Environment Variable

**For Windows PowerShell (Current Session):**
```powershell
$env:GOOGLE_API_KEY="paste_your_api_key_here"
```

**For Windows PowerShell (Permanent):**
```powershell
[Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "paste_your_api_key_here", "User")
```

**For Command Prompt:**
```cmd
set GOOGLE_API_KEY=paste_your_api_key_here
```

**For Linux/Mac:**
```bash
export GOOGLE_API_KEY="paste_your_api_key_here"
```

To make it permanent on Linux/Mac, add to `~/.bashrc` or `~/.zshrc`:
```bash
echo 'export GOOGLE_API_KEY="paste_your_api_key_here"' >> ~/.bashrc
source ~/.bashrc
```

### 4. Run the Application
```bash
cd E:\pdf_comparison\pdf_compare_ai_tool
streamlit run src/app/streamlit_app.py
```

### 5. Use the AI Summarization
1. In the sidebar, select **"Basic"** mode
2. Upload **PDF A** (first PDF file)
3. Upload **PDF B** (second PDF file)
4. Click the **"🤖 AI Summarize"** button
5. Wait for the summary to generate (10-30 seconds)
6. View the structured comparison summary
7. Download as **Markdown (.md)** or **PDF (.pdf)** format

## Example Usage

### Python Script
```python
import os
from pdf_compare_solution import generate_ai_summary

# Set your API key
os.environ['GOOGLE_API_KEY'] = 'your_api_key_here'

# Generate summary
summary = generate_ai_summary(
    pdf_a_path='path/to/first_product.pdf',
    pdf_b_path='path/to/second_product.pdf'
)

# Print or save the summary
print(summary)

# Save to file
with open('comparison_summary.md', 'w', encoding='utf-8') as f:
    f.write(summary)
```

## What You'll Get

The AI summary includes:

### 📋 Document Overview
- Product codes, brands, barcodes
- Country of origin
- Document metadata

### 🔧 Functional Differences
- Design variations
- Material changes
- Performance features
- Side-by-side comparison tables

### 📏 Dimensional Analysis
- Size comparisons (Width, Height, Depth)
- Weight differences
- Packaging details
- Change indicators (↑ Increase, ↓ Decrease, = Equal)

### 💼 Executive Insights
- Business impact summary
- Engineering implications
- Decision-making guidance

## Troubleshooting

### ❌ "Google API key not found"
**Solution:**
```powershell
# Windows - Set the variable
$env:GOOGLE_API_KEY="your_actual_key"

# Verify it's set
echo $env:GOOGLE_API_KEY
```

### ❌ "google-generativeai package not installed"
**Solution:**
```bash
pip install google-generativeai
```

### ❌ API Rate Limit Errors
**Solution:**
- Wait a few minutes and try again
- Check your API quota at https://console.cloud.google.com/
- Consider upgrading to paid tier for higher limits

### ❌ Empty or Poor Quality Summary
**Possible Causes:**
- PDFs contain only images (not text)
- PDFs are scanned documents without OCR
- PDFs are not product specification documents

**Solution:**
- Ensure PDFs contain selectable text
- Use text-based PDFs, not scanned images
- Works best with technical datasheets

## Tips for Best Results

✅ **Use Technical PDFs**: Product datasheets, specifications, catalogs
✅ **Ensure Text Quality**: Clear, selectable text in PDFs
✅ **Similar Documents**: Best when comparing similar product types
✅ **Complete Information**: PDFs with comprehensive specifications
✅ **Good Connection**: Stable internet for API calls

## Cost Information

**Free Tier:**
- 60 requests per minute
- 1,500 requests per day
- 1 million tokens per month

This is usually sufficient for regular use!

**Check Current Pricing:**
https://ai.google.dev/pricing

## Sample Output Preview

```markdown
# ✅ Automated Comparison Summary — Product Specification Docs

## **Document Overview**
| Field | Product A | Product B |
|-------|-----------|-----------|
| Brand | Acme Tools | Acme Tools |
| Product Code | AT-1234 | AT-1235 |
| Description | Heavy Duty Wrench | Extra Heavy Duty Wrench |

## **Key Functional & Feature Differences**
| Category | Product A | Product B |
|----------|-----------|-----------|
| Material | Carbon Steel | Alloy Steel |
| Torque Rating | 100 Nm | 150 Nm |

- Product B features upgraded alloy steel construction
- 50% increase in torque capacity
- Enhanced durability for industrial applications

... (and more sections)
```

## Need Help?

Check the detailed documentation:
- Full guide: `AI_SUMMARIZATION.md`
- Implementation details: `IMPLEMENTATION_SUMMARY.md`
- Environment setup: `.env.example`

## Privacy Note

⚠️ PDF content is sent to Google's Gemini API for processing. Do not use with confidential documents unless you have appropriate agreements with Google.
