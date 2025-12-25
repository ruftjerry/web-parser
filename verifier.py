import json
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL_SMART
from utils_logging import log_event, log_token_usage

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT_VERIFIER = """
You are a Senior Data Analyst reviewing extracted data for quality and completeness.

Your tasks:
1. Assess if we captured the domain-specific critical fields
2. Create a concise, high-value summary suitable for quick briefing
3. Identify any missing critical data
4. Provide qualitative assessment

Output JSON:
{
    "summary": "A concise summary of the item/page (2-3 sentences, business-focused)",
    "completeness_score": 0-100,
    "missing_critical_fields": ["field1", "field2"] or [],
    "analysis": "Your qualitative assessment of the data quality and insights"
}

Examples:

E-commerce listing:
{
    "summary": "Canon EOS R5 body, excellent condition, sold for $2,899 on Dec 15, 2024. Well below current market average of $3,200.",
    "completeness_score": 95,
    "missing_critical_fields": [],
    "analysis": "Strong deal - price is 9% below market. Fast sale suggests competitive pricing or high demand."
}

Product page:
{
    "summary": "Schiit Yggdrasil+ DAC, flagship R2R design with USB Gen 5 input. MSRP $2,799.",
    "completeness_score": 90,
    "missing_critical_fields": ["availability"],
    "analysis": "Complete product information extracted. Missing current stock status."
}

Be concise and business-focused in your summary.
"""

def verify_and_summarize(extracted_data: dict, context: dict) -> dict:
    """Verify extraction quality and create executive summary."""
    log_event(f"✅ Verifying extraction quality ({MODEL_SMART})...")
    
    payload = json.dumps({
        "original_context": context,
        "extracted_data": extracted_data
    }, indent=2, ensure_ascii=False)
    
    try:
        response = client.chat.completions.create(
            model=MODEL_SMART,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_VERIFIER},
                {"role": "user", "content": f"Review this extraction:\n\n{payload}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        usage = response.usage
        log_token_usage("Verification", MODEL_SMART, usage.prompt_tokens, usage.completion_tokens)
        
        review = json.loads(content)
        log_event(f"   Completeness: {review.get('completeness_score', 'N/A')}")
        
        return review
        
    except Exception as e:
        log_event(f"❌ Verification failed: {e}", "error")
        return {
            "summary": "Verification Failed", 
            "completeness_score": 0,
            "missing_critical_fields": [],
            "error": str(e)
        }