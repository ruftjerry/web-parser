import json
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL_SMART, MODEL_FAST
from utils_logging import log_event, log_token_usage

client = OpenAI(api_key=OPENAI_API_KEY)

# --- PROMPT 1: THE STRATEGIST (GPT-4o) ---
SYSTEM_PROMPT_CONTEXT = """
You are a Data Strategy Architect analyzing web pages for structured data extraction.

You receive:
1. JSON-LD structured data (if present - this is often the gold mine)
2. Complete cleaned HTML (full page structure, all classes preserved)

Your task: Analyze and understand this page deeply.

Determine:

**1. Domain** 
What industry/category is this? Be specific.
Examples: "Used Camera Equipment Marketplace", "Audio Equipment Retail", "Home Improvement Tools", "Real Estate Listings"

**2. Page Type** 
What is the PURPOSE of this specific page? Be very specific.

Multi-item pages:
- "Search Results" = User searched, seeing 10-50+ items
- "Category Page" = Browsing a category, seeing products
- "Comparison Page" = Side-by-side product comparisons

Single-item pages:
- "Single Product - Active" = One item currently for sale
- "Single Product - Sold" = Historical sold listing
- "Product Detail" = Manufacturer's product page

Content pages:
- "Article/Blog" = Written content
- "Review" = Product review or comparison
- "Specs/Documentation" = Technical specifications

**3. Critical Data Points**
What information is ESSENTIAL to extract from this type of page?

For marketplace listings: title, price, condition, date sold, seller
For product pages: name, price, specifications, availability
For reviews: product name, rating, pros/cons, recommendation

**4. Extraction Guidelines**
Provide SPECIFIC strategic guidance:

For multi-item pages:
- Identify the repeating container pattern you found in the HTML
- Specify which containers are PRODUCTS vs FILTERS/NAVIGATION
- Example: "Extract from .s-card elements (47 found), avoid .x-refine sidebar"

For single-item pages:
- Prioritize JSON-LD if complete
- Note which specs are in tables vs description text
- Example: "JSON-LD has price/title, specs table at #product-specs"

Output JSON:
{
    "domain": "Specific industry/category",
    "page_type": "Specific page type from above",
    "critical_fields": ["field1", "field2", "field3"],
    "extraction_guidelines": "Detailed strategic guidance with specific selectors/patterns you observed in the HTML"
}

Be thorough. The engineer will use your analysis to create the extraction plan.
"""

# --- PROMPT 2: THE ENGINEER (GPT-4o-mini) ---
SYSTEM_PROMPT_TECHNICAL = """
You are a CSS/JSON-LD Extraction Engineer.

You receive:
1. Complete cleaned HTML structure
2. Strategic guidelines from the Architect
3. JSON-LD data (if present)

Your job: Create SPECIFIC extraction selectors for each required field.

**CRITICAL RULES:**

1. **Prioritize JSON-LD when available**
   - Use JSONPath syntax: $.name, $.offers.price, $.brand.name
   - JSON-LD is more reliable than HTML scraping

2. **For CSS selectors, be SPECIFIC**
   - Use complete class paths: .s-item__price not just .price
   - Target the MAIN CONTENT, not filters/navigation/ads
   - Test your selector against the HTML provided

3. **Inspect the HTML carefully**
   - Look for repeating patterns (products list)
   - Find the ACTUAL classes used (don't assume)
   - Avoid common pitfalls (filter sidebars, navigation, ads)

4. **Common Mistakes to Avoid:**
   - Extracting filter options as product data (e.g., "Under $150" is a filter, not a price)
   - Using selectors that don't exist in the HTML
   - Targeting navigation/breadcrumbs instead of product containers
   - Missing data-* attributes (retailers often use these)

**Extraction Strategy by Page Type:**

Multi-item pages (Search Results, Category):
- Find the container that repeats for each product
- Extract from the FIRST instance to demonstrate the pattern
- The Python code will loop through all matching containers

Single-item pages (Product Detail):
- Extract the one product's complete information
- JSON-LD usually has most of what you need
- Use CSS for specs/details not in JSON-LD

**Output JSON Format:**
{
    "strategies": {
        "field_name": {
            "method": "json_ld" | "css",
            "selector": "$.json.path" | ".css.selector.path"
        }
    }
}

Examples:

Good CSS selector:
{
    "title": {
        "method": "css",
        "selector": ".s-item__title span"
    }
}

Good JSON-LD selector:
{
    "price": {
        "method": "json_ld",
        "selector": "$.offers.price"
    }
}

Mixed approach:
{
    "title": {"method": "json_ld", "selector": "$.name"},
    "specs": {"method": "css", "selector": "#product-specifications"}
}

Be precise. Your selectors must work on the HTML provided.
"""

def analyze_context(brief: dict) -> dict:
    """Step 1: GPT-4o analyzes the page to understand what it is."""
    log_event(f"🧠 Step 1: Context Analysis ({MODEL_SMART})...")
    
    # Create a structured payload
    payload = {
        "json_ld_data": brief.get("json_ld_data", []),
        "html_structure": brief.get("full_clean_html", ""),
        "size_info": {
            "original_kb": brief.get("original_size_kb", 0),
            "cleaned_kb": brief.get("cleaned_size_kb", 0),
            "estimated_tokens": brief.get("estimated_tokens", 0)
        }
    }
    
    brief_str = json.dumps(payload, indent=2, ensure_ascii=False)
    
    try:
        response = client.chat.completions.create(
            model=MODEL_SMART,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_CONTEXT},
                {"role": "user", "content": f"Analyze this page:\n\n{brief_str}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        content = response.choices[0].message.content
        usage = response.usage
        log_token_usage("Context Analysis", MODEL_SMART, usage.prompt_tokens, usage.completion_tokens)
        
        context = json.loads(content)
        log_event(f"   Domain: {context.get('domain', 'Unknown')}")
        log_event(f"   Page Type: {context.get('page_type', 'Unknown')}")
        
        return context
        
    except Exception as e:
        log_event(f"❌ Context Analysis failed: {e}", "error")
        raise

def create_technical_plan(brief: dict, context: dict) -> dict:
    """Step 2: GPT-4o-mini creates specific extraction selectors."""
    log_event(f"🔧 Step 2: Technical Planning ({MODEL_FAST})...")
    
    # Combine brief + context for the engineer
    payload = {
        "json_ld_data": brief.get("json_ld_data", []),
        "html_structure": brief.get("full_clean_html", ""),
        "strategic_context": context
    }
    
    combined_input = json.dumps(payload, indent=2, ensure_ascii=False)
    
    try:
        response = client.chat.completions.create(
            model=MODEL_FAST,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TECHNICAL},
                {"role": "user", "content": f"Create extraction plan:\n\n{combined_input}"}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )
        
        content = response.choices[0].message.content
        usage = response.usage
        log_token_usage("Technical Planning", MODEL_FAST, usage.prompt_tokens, usage.completion_tokens)
        
        plan = json.loads(content)
        log_event(f"   Created {len(plan.get('strategies', {}))} extraction strategies")
        
        return plan
        
    except Exception as e:
        log_event(f"❌ Technical Planning failed: {e}", "error")
        raise