"""
analyzer.py - GPT-4o-mini analyzes a sample of the page to form a hypothesis
"""

import json
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL_HYPOTHESIS
from utils_logging import log_event, log_token_usage

client = OpenAI(api_key=OPENAI_API_KEY)

HYPOTHESIS_PROMPT = """You are analyzing a web page for product/listing research.

Context:
- These are typically marketplace pages (eBay, Craigslist, Reverb, Facebook Marketplace, etc.)
- Or retail/brand product pages (Crutchfield, B&H, Micro Center, Canon, Schiit, etc.)
- Common categories: audio equipment, cameras, computers, woodworking tools, technology products
- But be flexible - it could be anything

Your task: Look at this HTML SAMPLE and form a hypothesis about what this page is.

Analyze:
1. What kind of page is this? (search results, single product, category listing, auction results, etc.)
2. What source/marketplace/website?
3. What product category or domain?
4. Single item or multiple items? If multiple, approximately how many?
5. What data fields would be valuable to extract?
6. How confident are you in this assessment?

Be specific and observant. Your hypothesis will guide the extraction.

Return ONLY valid JSON in this format:
{
  "page_type": "descriptive page type",
  "source": "website/marketplace name",
  "category": "product category",
  "item_count": "single" or "multiple (estimate)",
  "expected_fields": ["field1", "field2", ...],
  "confidence": "high/medium/low",
  "notes": "any important observations"
}
"""

def analyze_page(html_sample: str) -> dict:
    """
    GPT-4o-mini analyzes a sample of HTML to form a hypothesis about the page.
    
    Args:
        html_sample: First ~50KB of cleaned HTML
        
    Returns:
        dict with hypothesis about page type, source, expected data, etc.
    """
    log_event("🔍 Step 2A: Forming Hypothesis (GPT-4o-mini)...")
    
    try:
        response = client.chat.completions.create(
            model=MODEL_HYPOTHESIS,
            messages=[
                {"role": "system", "content": HYPOTHESIS_PROMPT},
                {"role": "user", "content": f"HTML Sample:\n\n{html_sample}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        usage = response.usage
        log_token_usage("Hypothesis", MODEL_HYPOTHESIS, usage.prompt_tokens, usage.completion_tokens)
        
        hypothesis = json.loads(content)
        
        log_event(f"   📋 Page Type: {hypothesis.get('page_type', 'Unknown')}")
        log_event(f"   🌐 Source: {hypothesis.get('source', 'Unknown')}")
        log_event(f"   📦 Category: {hypothesis.get('category', 'Unknown')}")
        log_event(f"   🔢 Items: {hypothesis.get('item_count', 'Unknown')}")
        log_event(f"   ✅ Confidence: {hypothesis.get('confidence', 'Unknown')}")
        
        return hypothesis
        
    except Exception as e:
        log_event(f"❌ Hypothesis generation failed: {e}", "error")
        raise