import json
from bs4 import BeautifulSoup
from jsonpath_ng import parse
from utils_logging import log_event

def execute_extraction(raw_html: str, brief: dict, plan: dict) -> dict:
    """
    Execute extraction using the plan created by the planner.
    
    Uses:
    - Raw HTML for JSON-LD extraction (to access original script tags)
    - Cleaned HTML for CSS selectors (to match what the planner saw)
    """
    log_event("⚙️  Executing extraction plan...")
    
    # Parse BOTH versions of the HTML
    raw_soup = BeautifulSoup(raw_html, "lxml")
    cleaned_html = brief.get("full_clean_html", raw_html)
    cleaned_soup = BeautifulSoup(cleaned_html, "lxml")
    
    strategies = plan.get("strategies", {})
    extracted_data = {}
    
    # Get JSON-LD data
    json_ld_blobs = brief.get("json_ld_data", [])
    
    # Backup: try to extract from raw HTML if brief didn't have it
    if not json_ld_blobs:
        for script in raw_soup.find_all("script", type="application/ld+json"):
            try:
                json_ld_blobs.append(json.loads(script.string))
            except:
                pass
    
    log_event(f"   Processing {len(strategies)} extraction strategies...")
    successful_extractions = 0
    
    for field, strategy in strategies.items():
        method = strategy.get("method")
        selector = strategy.get("selector")
        
        try:
            if method == "json_ld":
                # JSONPath extraction from structured data
                jsonpath_expression = parse(selector)
                found = False
                
                for blob in json_ld_blobs:
                    match = jsonpath_expression.find(blob)
                    if match:
                        extracted_data[field] = match[0].value
                        found = True
                        successful_extractions += 1
                        break
                
                if not found:
                    log_event(f"      ⚠️  JSON-LD path '{selector}' not found for '{field}'", "warning")
                    extracted_data[field] = None

            elif method == "css":
                # CSS selector extraction from cleaned HTML
                # Use cleaned HTML because that's what the planner saw
                element = cleaned_soup.select_one(selector)
                
                if element:
                    extracted_data[field] = element.get_text(strip=True)
                    successful_extractions += 1
                else:
                    log_event(f"      ⚠️  CSS selector '{selector}' not found for '{field}'", "warning")
                    extracted_data[field] = None
            
            else:
                log_event(f"      ⚠️  Unknown method '{method}' for '{field}'", "warning")
                extracted_data[field] = None
                    
        except Exception as e:
            log_event(f"      ❌ Error extracting field '{field}': {e}", "warning")
            extracted_data[field] = "Error"

    success_rate = (successful_extractions / len(strategies) * 100) if strategies else 0
    log_event(f"   Extraction complete: {successful_extractions}/{len(strategies)} successful ({success_rate:.1f}%)")
    
    return extracted_data