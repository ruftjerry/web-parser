"""
formatter.py - GPT-4o-mini formats extracted data into comprehensive markdown
"""

import json
from pathlib import Path
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL_FORMATTER
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

FORMATTER_PROMPT = f"""{USER_CONTEXT}

YOUR SPECIFIC TASK: FORMATTING

You are a data formatter. Your job is to convert extracted JSON data into clean, comprehensive markdown.

Your task:
1. Take the raw extracted data (JSON)
2. Format it into readable markdown
3. Include EVERY item and ALL their fields
4. Be factual and straightforward - no analysis or recommendations yet
5. Use clear structure with headers and sections

Guidelines:
- For multi-item data: List every single item with all its details
- Use natural formatting (tables, lists, sections - whatever fits the data)
- Keep field names clear and consistent
- Don't skip any items or fields
- Don't add commentary - just present the data cleanly

Example for marketplace listings:
```markdown
## All Items Found

### Item 1: [Product Name]
- **Price:** $X.XX
- **Condition:** [condition]
- **Seller:** [seller name]
- **Shipping:** [shipping info]
- **Link:** [url if available]

### Item 2: [Product Name]
...continue for ALL items...

Example for product specs:

## Product Specifications

**Model:** [model]
**Features:**
- Feature 1: [detail]
- Feature 2: [detail]
...all features...

Return ONLY the formatted markdown content. No JSON wrapper, no explanations.
The markdown should be complete and ready to insert into a report.
"""

def format_data(hypothesis: dict, extracted_data: dict) -> str:
    """
    GPT-4o-mini formats the extracted data into comprehensive markdown.

    Args:
        hypothesis: The hypothesis about what was extracted
        extracted_data: Raw JSON data from Gemini
        
    Returns:
        str: Formatted markdown content
    """
    log_event("📝 Step 3A: Formatting Data (GPT-4o-mini)...")

    # Provide context about what was extracted
    context = {
        "page_type": hypothesis.get('page_type', 'unknown'),
        "source": hypothesis.get('source', 'unknown'),
        "item_count": hypothesis.get('item_count', 'unknown'),
        "data": extracted_data
    }

    try:
        response = client.chat.completions.create(
            model=MODEL_FORMATTER,
            messages=[
                {"role": "system", "content": FORMATTER_PROMPT},
                {"role": "user", "content": json.dumps(context, indent=2)}
            ],
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        usage = response.usage
        log_token_usage("Formatting", MODEL_FORMATTER, usage.prompt_tokens, usage.completion_tokens)
        
        # Count how many items were mentioned in the formatted output
        if 'items' in extracted_data:
            expected_count = len(extracted_data['items'])
            log_event(f"   ✅ Formatted {expected_count} items into markdown")
        else:
            log_event(f"   ✅ Formatted data into markdown")
        
        return content
        
    except Exception as e:
        log_event(f"❌ Formatting failed: {e}", "error")
        raise