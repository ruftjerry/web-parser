# 🔍 Smart HTML Extraction Pipeline

**Intelligent web scraping with AI-powered two-step validation**

## 🎯 What This Does

Drop an HTML file into a folder → Get structured data extracted automatically with AI validation

The system:
1. **Cleans** the HTML (removes Base64, CSS, JavaScript bloat)
2. **Forms Hypothesis** (GPT-4o-mini analyzes what kind of page this is)
3. **Extracts Data** (Gemini 2.5 Flash with 1M token context window)
4. **Formats Results** (GPT-4o-mini converts JSON to readable markdown)
5. **Validates & Adds Insights** (GPT-4o reviews quality and adds strategic analysis)
6. **Generates Reports** (Markdown + JSON + Debug files)

## 💰 Cost Structure

### Per-Page Processing
- **Hypothesis Formation**: ~$0.0005-0.001 (GPT-4o-mini on 50KB sample)
- **Data Extraction**: ~$0.001-0.003 (Gemini 2.5 Flash on full HTML)
- **Formatting**: ~$0.0005-0.001 (GPT-4o-mini converts to markdown)
- **Validation & Insights**: ~$0.02-0.05 (GPT-4o strategic review)
- **Total: ~$0.03-0.06 per page**

### Real-World Examples

**Researching 50 eBay sold listings:**
- 50 pages × $0.04 average = **$2.00 total** ($0.04/page)

**Checking prices across 3 different sites:**
- 10 Schiit pages: 10 × $0.04 = $0.40
- 10 Emotiva pages: 10 × $0.04 = $0.40
- 20 Crutchfield pages: 20 × $0.04 = $0.80
- **Total: $1.60 for 40 pages**

**Analyzing product specifications:**
- Complex product page with specs: ~$0.05
- Simple listing page: ~$0.03

## 📁 Directory Structure

```
your_project/
├── Pi_Inbox/
│   ├── Research_Queue/       ← DROP HTML FILES HERE
│   ├── Processed_Archive/    ← Successfully processed files
│   ├── Errors/                ← Failed processing files
│   └── Output/                ← Reports (MD + JSON + DEBUG)
├── config.py
├── main_runner.py
├── analyzer.py                ← Hypothesis formation
├── gemini_extractor.py        ← Data extraction (Gemini)
├── formatter.py               ← Markdown formatting
├── validator.py               ← Quality validation + insights
├── reporter.py                ← Report generation
├── html_brief.py              ← HTML cleaning
├── utils_logging.py
├── .env                       ← Your API keys
├── research_pipeline.log      ← Activity log
└── token_usage_log.csv        ← Cost tracking
```

## 🚀 Setup

### 1. Install Dependencies

```bash
pip install openai google-generativeai beautifulsoup4 lxml watchdog python-dotenv --break-system-packages
```

### 2. Configure API Keys

Create a `.env` file:

```
OPENAI_API_KEY=sk-your-key-here
GOOGLEAISTUDIO_API_KEY=your-google-api-key-here
```

**Get API Keys:**
- OpenAI: https://platform.openai.com/api-keys
- Google AI Studio: https://aistudio.google.com/app/apikey

### 3. Create Directories

```bash
mkdir -p Pi_Inbox/Research_Queue
mkdir -p Pi_Inbox/Processed_Archive
mkdir -p Pi_Inbox/Errors
mkdir -p Pi_Inbox/Output
```

### 4. Start the Pipeline

```bash
python main_runner.py
```

You'll see:
```
🚀 SMART EXTRACTION PIPELINE - STARTED
📂 Monitoring: /path/to/Pi_Inbox/Research_Queue

🔧 API Configuration (Two-Step Validation):
   Hypothesis:  gpt-4o-mini (classification)
   Extraction:  gemini-2.5-flash (big context)
   Formatting:  gpt-4o-mini (mechanical work)
   Validation:  gpt-4o (strategic insights)

⏳ Waiting for HTML files...
```

## 📥 How to Use

### Save Web Pages as HTML

**Chrome/Safari:**
1. Visit the page (eBay listing, product page, etc.)
2. Right-click → "Save As..."
3. Format: "Webpage, Complete" or "Web Archive"
4. Save to: `Pi_Inbox/Research_Queue/`

**Or use browser extensions:**
- SingleFile (Chrome/Firefox) - captures everything in one HTML file
- Save Page WE (Firefox)

### Watch It Process

The system automatically detects new files and processes them:

```
📥 New file detected: ebay_nikon_d850.html
   ⏳ Waiting for file transfer to complete...
   ✅ Transfer complete: 1247.3 KB

🚀 Processing: ebay_nikon_d850.html
   File size: 1247.3 KB

📋 Step 1: Reading and Cleaning HTML...
   📄 Processing HTML: 1,276,842 characters (1247.3 KB)
   ✅ Found 2 JSON-LD structured data blocks
   🗑️ Removed 247 non-content tags
   🗑️ Removed 89 HTML comments
   🖼️ Removed 12 Base64 inline images
   ✅ Cleaning complete: 1247.3KB → 324.8KB (74.0% reduction)
   📊 Estimated tokens: ~81,200

🔍 Step 2A: Forming Hypothesis (GPT-4o-mini)...
   📋 Page Type: Search results / category listing
   🌐 Source: eBay
   📦 Category: Camera equipment
   🔢 Items: multiple (24 items visible)
   ✅ Confidence: high
   💰 Cost: $0.0008 (4,103 in, 89 out)

⚡ Step 2B: Extracting Data (Gemini gemini-2.5-flash)...
   📦 Extracted 24 items
   💰 Cost: $0.0061 (81,234 in, 412 out)

📝 Step 3A: Formatting Data (GPT-4o-mini)...
   ✅ Formatted 24 items into markdown
   💰 Cost: $0.0012 (6,847 in, 1,234 out)

✅ Step 3B: Validation & Insights (GPT-4o)...
   ✅ Status: SUCCESS
   📊 Items: 24
   ⭐ Quality: excellent
   💰 Cost: $0.0287 (1,024 in, 243 out)

📊 Step 4: Generating Reports...
   📄 Generated reports:
      - 20241225-1430_ebay_nikon_d850.md
      - 20241225-1430_ebay_nikon_d850.json
      - 20241225-1430_ebay_nikon_d850_DEBUG.json

✅ SUCCESS - Archived: ebay_nikon_d850.html
```

### Check Your Results

**Markdown Report** (human-readable):
- Page analysis (type, source, category)
- Executive summary
- Key findings and insights
- All extracted data formatted cleanly
- Validation notes
- Recommendation

**JSON File** (for scripts/databases):
- Complete structured data
- Metadata (timestamp, source, status)
- Hypothesis details
- Validation results
- Statistical insights

**Debug File** (troubleshooting):
- Full hypothesis
- Raw extracted data
- Formatted markdown length
- Complete validation result

## 📊 Cost Tracking

All API calls are logged to `token_usage_log.csv`:

```csv
Timestamp,Task,Model,Input_Tokens,Output_Tokens,Cost_USD
2024-12-25T14:30:15,Hypothesis,gpt-4o-mini,4103,89,$0.000818
2024-12-25T14:30:18,Extraction,gemini-2.5-flash,81234,412,$0.006216
2024-12-25T14:30:20,Formatting,gpt-4o-mini,6847,1234,$0.001767
2024-12-25T14:30:22,Validation & Insights,gpt-4o,1024,243,$0.028700
```

Import into Excel/Google Sheets to analyze spending patterns.

## 🎯 Understanding the Two-Step Validation Approach

### Why This Architecture?

The pipeline uses a smart division of labor:

1. **Fast Classification** (GPT-4o-mini)
   - Quickly understands what kind of page this is
   - Costs pennies, runs in seconds
   - Creates targeted extraction strategy

2. **Big Context Extraction** (Gemini 2.5 Flash)
   - Handles massive HTML (up to 1M tokens)
   - Cheap per-token pricing
   - Can see entire page structure at once

3. **Mechanical Formatting** (GPT-4o-mini)
   - Converts JSON to readable markdown
   - Straightforward task, cheap model
   - Ensures consistent output format

4. **Strategic Oversight** (GPT-4o)
   - Reviews extraction quality
   - Adds executive summary
   - Identifies patterns and insights
   - Only model that "thinks strategically"

### Cost/Quality Tradeoff

- **Cheaper alternative**: Skip validation step
  - Saves ~$0.02-0.05 per page
  - Risk: You won't know if extraction is incomplete
  
- **Premium option**: Use GPT-4o for everything
  - Costs ~$0.15-0.25 per page
  - Benefit: Slightly better hypothesis formation

Current setup is optimized for **best quality at reasonable cost**.

## 🛠️ Configuration Options

Edit `config.py` to adjust models:

```python
# Model Strategies (TWO-STEP VALIDATION)
MODEL_HYPOTHESIS = "gpt-4o-mini"        # OpenAI - cheap classification
MODEL_CONTEXT = "gemini-2.5-flash"      # Google - 1M token window
MODEL_FORMATTER = "gpt-4o-mini"         # OpenAI - mechanical formatting
MODEL_VALIDATOR = "gpt-4o"              # OpenAI - strategic validation
```

**Alternative configurations:**

**Budget Mode** (skip validation):
```python
# Comment out validation step in main_runner.py
# Saves ~50% on costs, but no quality checking
```

**Premium Mode** (GPT-4o everywhere):
```python
MODEL_HYPOTHESIS = "gpt-4o"
MODEL_FORMATTER = "gpt-4o"
# Total cost: ~$0.15-0.25 per page
```

## 🐛 Troubleshooting

### "Context length exceeded" error
- Your HTML is extremely large (>1M tokens)
- Solution: Gemini 2.5 Flash should handle most pages, but try saving as "Webpage, HTML Only" instead of "Complete"

### Low item counts extracted
- Check `*_DEBUG.json` to see raw extraction
- Page structure might be unusual
- Review hypothesis to see if page type was correctly identified

### Formatting looks wrong
- Check the formatted_markdown section in DEBUG file
- Formatter might need prompt adjustment for this data type
- Validation should flag formatting issues

### API errors
- Check your API keys in `.env`
- Verify you have credits on both OpenAI and Google AI Studio
- Check `research_pipeline.log` for detailed error messages

## 📈 What Pages Work Best

**Excellent (24+ items, 95%+ accuracy):**
- eBay sold listings / search results
- Amazon search results
- Marketplace category pages
- Multi-item comparison pages

**Very Good (Single items, 90%+ accuracy):**
- Individual product pages (Schiit, Emotiva, etc.)
- Retailer product details (Crutchfield, B&H)
- Specification sheets
- Auction item pages

**Good (80-90% accuracy):**
- Review sites (complex layouts)
- Forum threads (varied structure)
- Category listings with ads mixed in

**Fair (May need review):**
- JavaScript-heavy dynamic sites (save after page fully loads)
- Sites with heavy anti-scraping (may have incomplete HTML)
- Multi-tab interfaces (only saves active tab)

## 🎓 Advanced Usage

### Batch Processing

Drop multiple files at once:
```bash
cp ~/Downloads/ebay_listings/*.html Pi_Inbox/Research_Queue/
```

The system processes them sequentially, one at a time.

### Integration with Other Tools

The JSON output is perfect for:
- Python scripts (pandas, data analysis)
- Spreadsheets (import JSON)
- Databases (insert structured data)
- Price tracking systems

Example Python usage:
```python
import json

with open('Pi_Inbox/Output/20241225-1430_ebay_camera.json') as f:
    data = json.load(f)
    
# Access extracted data
items = data['extracted_data']['items']
for item in items:
    print(f"Title: {item.get('title')}")
    print(f"Price: {item.get('price')}")
    print(f"Condition: {item.get('condition')}")
    print("---")
```

### Understanding the Pipeline Flow

```
HTML File Dropped
    ↓
[html_brief.py] Clean HTML, extract JSON-LD
    ↓
[analyzer.py] GPT-4o-mini: "What is this page?"
    ↓
[gemini_extractor.py] Gemini: Extract all items
    ↓
[formatter.py] GPT-4o-mini: Convert to markdown
    ↓
[validator.py] GPT-4o: Check quality + add insights
    ↓
[reporter.py] Generate MD + JSON + DEBUG files
    ↓
File moved to Processed_Archive or Errors
```

## 💡 Tips & Tricks

1. **Name your HTML files descriptively**
   - Good: `ebay_nikon_d850_sold_dec2024.html`
   - Bad: `page.html`
   - The filename appears in all reports

2. **Save pages after they fully load**
   - Wait for images, prices, and dynamic content
   - Some sites load data via JavaScript
   - Watch for "loading..." indicators

3. **Check the hypothesis first**
   - Look at the console output when processing
   - If page_type is wrong, extraction might miss data
   - Confidence should be "high" for best results

4. **Review validation status**
   - SUCCESS = extraction matched expectations
   - INCOMPLETE = got some data but not all
   - FAILED = something went wrong

5. **Use JSON-LD when available**
   - Many sites include structured data (JSON-LD)
   - Pipeline automatically extracts these
   - Mentioned in cleaning step: "Found 2 JSON-LD blocks"

6. **Monitor costs via CSV**
   - `token_usage_log.csv` tracks every API call
   - Import to Excel to see cost trends
   - Gemini extraction is usually the cheapest step

## 🔍 Quality Indicators

Check the validation section of your markdown reports:

**Excellent Quality:**
```
✅ Status: SUCCESS
📊 Items: 24/24 extracted
⭐ Quality: excellent
```

**Good Quality:**
```
✅ Status: SUCCESS
📊 Items: 22/24 extracted
⭐ Quality: good
Note: 2 items missing shipping info
```

**Needs Review:**
```
⚠️ Status: INCOMPLETE
📊 Items: 18/24 extracted
⚠️ Quality: fair
Problem: Some items missing prices
```

## 📞 Questions?

Check the logs:
- `research_pipeline.log` - detailed activity log with timestamps
- `token_usage_log.csv` - every API call and cost
- `*_DEBUG.json` - per-file extraction details and raw data

**Common Issues:**

| Symptom | Check | Solution |
|---------|-------|----------|
| No files processing | Queue directory path | Verify `QUEUE_DIR` in config.py |
| API errors | `.env` file | Confirm both API keys are valid |
| Incomplete extractions | DEBUG JSON | Review hypothesis and raw extraction |
| High costs | CSV log | Check which model is using most tokens |
| Files in Errors folder | `research_pipeline.log` | Look for error messages |

---

**Built for accuracy. Optimized for cost. Powered by AI.**

*Two-step validation: Fast classification meets deep extraction with strategic oversight.*