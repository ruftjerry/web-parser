"""
gemini_extractor.py - Gemini 2.5 Flash extracts data based on hypothesis
"""

import json
from google import genai
from config import GOOGLE_API_KEY, MODEL_CONTEXT
from utils_logging import log_event, log_token_usage

client = genai.Client(api_key=GOOGLE_API_KEY)

def create_extraction_prompt(hypothesis: dict) -> str:
    """
    Create a targeted extraction prompt based on the hypothesis.
    """
    page_type = hypothesis.get('page_type', 'unknown page')
    source = hypothesis.get('source', 'unknown source')
    category = hypothesis.get('category', 'unknown category')
    item_count = hypothesis.get('item_count', 'unknown')
    expected_fields = hypothesis.get('expected_fields', [])
    
    prompt = f"""You are extracting data from a web page for product research.

HYPOTHESIS (from initial analysis):
- Page Type: {page_type}
- Source: {source}
- Category: {category}
- Expected Items: {item_count}
- Expected Fields: {', '.join(expected_fields)}

YOUR TASK:
Extract ALL relevant data from this page. 

If this is a MULTI-ITEM page (search results, category listing, etc.):
- Extract EVERY item/product/listing you find
- Return a JSON array with all items
- Do not skip any items

If this is a SINGLE-ITEM page (product detail, single listing, etc.):
- Extract all relevant product data
- Return a JSON object with the item data

IMPORTANT:
- Be thorough - get all items, not just the first few
- Extract the fields mentioned in the hypothesis, plus any other valuable data you see
- Use clear, descriptive field names
- If you find more fields than expected, include them
- Return ONLY valid JSON, no markdown, no explanation

For multi-item pages, return:
{{
  "items": [
    {{"field1": "value1", "field2": "value2", ...}},
    {{"field1": "value1", "field2": "value2", ...}},
    ...
  ]
}}

For single-item pages, return:
{{
  "item": {{"field1": "value1", "field2": "value2", ...}}
}}
"""
    return prompt

def extract_data(full_html: str, hypothesis: dict) -> dict:
    """
    Gemini 2.5 Flash extracts data from the full HTML based on hypothesis.
    
    Args:
        full_html: Complete cleaned HTML (can be 500KB+)
        hypothesis: The hypothesis from analyzer.py
        
    Returns:
        dict with extracted data
    """
    log_event(f"⚡ Step 2B: Extracting Data (Gemini {MODEL_CONTEXT})...")
    
    prompt = create_extraction_prompt(hypothesis)
    
    try:
        response = client.models.generate_content(
            model=MODEL_CONTEXT,
            contents=f"{prompt}\n\nHTML:\n{full_html}",
            config={
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        )
        
        content = response.text
        
        # Log token usage
        if hasattr(response, 'usage_metadata'):
            input_tokens = response.usage_metadata.prompt_token_count
            output_tokens = response.usage_metadata.candidates_token_count
            log_token_usage("Extraction", MODEL_CONTEXT, input_tokens, output_tokens)
        else:
            # Fallback estimation
            estimated_input = len(full_html) // 4
            estimated_output = len(content) // 4
            log_token_usage("Extraction", MODEL_CONTEXT, estimated_input, estimated_output)
        
        extracted = json.loads(content)
        
        # Log what we got
        if 'items' in extracted:
            item_count = len(extracted['items'])
            log_event(f"   📦 Extracted {item_count} items")
        elif 'item' in extracted:
            log_event(f"   📦 Extracted 1 item (single-item page)")
        else:
            log_event(f"   ⚠️  Unexpected extraction format", "warning")
        
        return extracted
        
    except json.JSONDecodeError as e:
        log_event(f"❌ Failed to parse Gemini response as JSON: {e}", "error")
        log_event(f"   Raw response: {content[:500]}...", "error")
        raise
    except Exception as e:
        log_event(f"❌ Extraction failed: {e}", "error")
        raise