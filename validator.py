"""
validator.py - GPT-4o validates formatted report and adds strategic insights
"""

import json
from pathlib import Path
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL_VALIDATOR
from utils_logging import log_event, log_token_usage

client = OpenAI(api_key=OPENAI_API_KEY)

# Load user context at module initialization
def _load_user_context():
    """Load the user context file for validation guidance."""
    context_path = Path(__file__).parent / 'user_context_validation.txt'
    if context_path.exists():
        return context_path.read_text()
    else:
        log_event("⚠️  user_context_validation.txt not found - proceeding without context", "warning")
        return ""

USER_CONTEXT = _load_user_context()

VALIDATOR_PROMPT = f"""{USER_CONTEXT}

YOUR SPECIFIC TASK: VALIDATION & INSIGHTS

You are a senior analyst reviewing a data extraction report.

You will receive:
1. HYPOTHESIS - What we expected to find
2. FORMATTED DATA - Already formatted markdown with all the extracted items
3. RAW EXTRACTION - The original JSON for reference

Your job:
1. Validate: Does the extraction match expectations? Is it complete?
2. Quality check: Any obvious problems or missing data?
3. Add value: Write executive summary and key insights (2-3 sentences each)

DO NOT reformat the data - it's already been formatted.
DO NOT rewrite the detailed listings - they're already there.
Just add strategic oversight and insights at the top.

Return ONLY valid JSON in this format:

For SUCCESSFUL extraction:
{{
  "status": "success",
  "validation": {{
    "hypothesis_match": true,
    "expected_items": "number or 'single'",
    "actual_items": number,
    "data_quality": "excellent/good/fair/poor",
    "completeness": "all items formatted" or "issue description",
    "notes": "any observations"
  }},
  "insights": {{
    "executive_summary": "2-3 sentence overview of what was found and why it matters",
    "key_findings": "2-3 notable patterns, trends, or important details from the data",
    "recommendation": "brief actionable next step or consideration"
  }},
  "statistics": {{
    "total_items": number,
    "key_metrics": "any relevant stats (price range, date range, condition breakdown, etc.)"
  }}
}}

For FAILED/INCOMPLETE extraction:
{{
  "status": "extraction_failed" or "extraction_incomplete",
  "validation": {{
    "hypothesis_match": false,
    "problem": "clear description of what went wrong",
    "expected_items": "what we expected",
    "actual_items": "what we got",
    "data_quality": "poor"
  }},
  "user_message": "Clear explanation of what failed",
  "partial_insights": {{
    "summary": "what WAS extracted, if useful"
  }}
}}

Be honest and concise. The formatted data speaks for itself - you're just adding the strategic layer.
"""

def validate_report(hypothesis: dict, extracted_data: dict, formatted_markdown: str, original_filename: str) -> dict:
    """
    GPT-4o validates the formatted report and adds strategic insights.
    
    Args:
        hypothesis: The hypothesis from analyzer.py
        extracted_data: Raw extraction from Gemini
        formatted_markdown: The formatted markdown from formatter.py
        original_filename: Original HTML filename for context
        
    Returns:
        dict with validation results, insights, and statistics
    """
    log_event(f"✅ Step 3B: Validation & Insights (GPT-4o)...")
    
    payload = {
        "hypothesis": hypothesis,
        "formatted_data_preview": formatted_markdown[:3000] + ("..." if len(formatted_markdown) > 3000 else ""),
        "raw_extraction_summary": {
            "items_count": len(extracted_data.get('items', [])) if 'items' in extracted_data else 1,
            "has_items": 'items' in extracted_data,
            "top_level_keys": list(extracted_data.keys())
        },
        "source_file": original_filename
    }
    
    try:
        response = client.chat.completions.create(
            model=MODEL_VALIDATOR,
            messages=[
                {"role": "system", "content": VALIDATOR_PROMPT},
                {"role": "user", "content": json.dumps(payload, indent=2)}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        content = response.choices[0].message.content
        usage = response.usage
        log_token_usage("Validation & Insights", MODEL_VALIDATOR, usage.prompt_tokens, usage.completion_tokens)
        
        result = json.loads(content)
        
        status = result.get('status', 'unknown')
        
        if status == 'success':
            validation = result.get('validation', {})
            actual_items = validation.get('actual_items', 'unknown')
            quality = validation.get('data_quality', 'unknown')
            
            log_event(f"   ✅ Status: SUCCESS")
            log_event(f"   📊 Items: {actual_items}")
            log_event(f"   ⭐ Quality: {quality}")
        else:
            problem = result.get('validation', {}).get('problem', 'Unknown issue')
            log_event(f"   ⚠️  Status: {status.upper()}", "warning")
            log_event(f"   ❌ Problem: {problem}", "warning")
        
        return result
        
    except Exception as e:
        log_event(f"❌ Validation failed: {e}", "error")
        raise
