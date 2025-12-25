"""
validator_reporter.py - GPT-4o validates extraction and creates beautiful reports
"""

import json
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL_VERIFY
from utils_logging import log_event, log_token_usage

client = OpenAI(api_key=OPENAI_API_KEY)

VALIDATION_PROMPT = """You are validating and reporting on web page data extraction.

You will receive:
1. HYPOTHESIS - What we thought the page was
2. EXTRACTED DATA - What Gemini actually extracted

Your job:
1. Validate: Does the extracted data match our hypothesis?
2. Assess quality: Is the extraction complete and accurate?
3. Create report: Provide executive summary and insights

VALIDATION CRITERIA:
- Does item count match expectations? (if multi-item page)
- Are expected fields present?
- Does data quality look good?
- Any obvious problems or red flags?

Return ONLY valid JSON in this format:

For SUCCESSFUL extraction:
{
  "status": "success",
  "validation": {
    "hypothesis_match": true,
    "expected_items": "from hypothesis",
    "actual_items": number,
    "expected_fields_found": ["field1", "field2"],
    "missing_fields": ["field3"],
    "data_quality": "excellent/good/fair/poor",
    "notes": "any observations"
  },
  "report": {
    "summary": "Executive summary - 2-3 sentences about what was found",
    "statistics": {
      "total_items": number,
      "key_metrics": "any relevant stats (avg price, date range, etc.)"
    },
    "insights": "2-3 key insights or notable findings",
    "recommendation": "what the user should know or do next"
  }
}

For FAILED/INCOMPLETE extraction:
{
  "status": "extraction_failed" or "extraction_incomplete",
  "validation": {
    "hypothesis_match": false,
    "problem": "clear description of what went wrong",
    "expected_items": "what we expected",
    "actual_items": "what we got",
    "data_quality": "poor"
  },
  "user_message": "Clear, actionable message to the user about what failed and what to do",
  "partial_report": {
    "summary": "brief summary of what WAS extracted, if anything useful"
  }
}

Be honest and direct. If extraction failed, say so clearly and suggest next steps.
"""

def validate_and_report(hypothesis: dict, extracted_data: dict, original_filename: str) -> dict:
    """
    GPT-4o validates the extraction against hypothesis and creates a detailed report.
    
    Args:
        hypothesis: The hypothesis from analyzer.py
        extracted_data: The data extracted by gemini_extractor.py
        original_filename: Original HTML filename for context
        
    Returns:
        dict with validation results and report
    """
    log_event(f"✅ Step 3: Validation & Report (GPT-4o)...")
    
    payload = {
        "hypothesis": hypothesis,
        "extracted_data": extracted_data,
        "source_file": original_filename
    }
    
    try:
        response = client.chat.completions.create(
            model=MODEL_VERIFY,
            messages=[
                {"role": "system", "content": VALIDATION_PROMPT},
                {"role": "user", "content": json.dumps(payload, indent=2)}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        content = response.choices[0].message.content
        usage = response.usage
        log_token_usage("Validation & Report", MODEL_VERIFY, usage.prompt_tokens, usage.completion_tokens)
        
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


def create_summary_message(result: dict) -> str:
    """
    Create a concise summary message for logging.
    """
    status = result.get('status', 'unknown')
    
    if status == 'success':
        report = result.get('report', {})
        summary = report.get('summary', 'Extraction successful')
        return f"✅ {summary}"
    else:
        user_msg = result.get('user_message', 'Extraction failed')
        return f"⚠️  {user_msg}"