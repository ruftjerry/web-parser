import json
from datetime import datetime
from pathlib import Path
from config import OUTPUT_DIR
from utils_logging import log_event

def generate_report(filename: str, extracted_data: dict, plan: dict, review: dict, context: dict, report_info: dict = None):
    """
    Generate comprehensive reports with cost tracking and cache statistics.
    
    Outputs:
    1. Markdown report (human-readable)
    2. JSON data file (machine-readable)
    3. Debug file (troubleshooting)
    """
    
    # Ensure output directory exists
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate timestamp for unique filenames
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    original_stem = Path(filename).stem
    safe_name = f"{timestamp}_{original_stem}"
    
    output_md_path = OUTPUT_DIR / f"{safe_name}.md"
    output_json_path = OUTPUT_DIR / f"{safe_name}.json"
    debug_path = OUTPUT_DIR / f"{safe_name}_DEBUG.txt"
    
    # Extract report info
    cache_hit = report_info.get("cache_hit", False) if report_info else False
    fingerprint = report_info.get("fingerprint", "N/A") if report_info else "N/A"
    completeness = report_info.get("completeness", 0) if report_info else 0
    
    # --- 1. SAVE FULL JSON DATA ---
    full_record = {
        "meta": {
            "timestamp": timestamp,
            "original_file": filename,
            "domain": context.get("domain", "Unknown"),
            "page_type": context.get("page_type", "Unknown"),
            "cache_hit": cache_hit,
            "fingerprint": fingerprint,
            "completeness_score": completeness
        },
        "context": context,
        "extraction_plan": plan,
        "extracted_data": extracted_data,
        "review": review
    }
    
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(full_record, f, indent=2, ensure_ascii=False)
    
    # --- 2. SAVE DEBUG FILE ---
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("EXTRACTION DEBUG REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"File: {filename}\n")
        f.write(f"Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Cache Hit: {'YES ✓' if cache_hit else 'NO - Full Analysis'}\n")
        f.write(f"Fingerprint: {fingerprint}\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("CONTEXT ANALYSIS\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Domain: {context.get('domain', 'Unknown')}\n")
        f.write(f"Page Type: {context.get('page_type', 'Unknown')}\n")
        f.write(f"Critical Fields: {', '.join(context.get('critical_fields', []))}\n")
        f.write(f"Guidelines: {context.get('extraction_guidelines', 'None')}\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("EXTRACTION STRATEGIES\n")
        f.write("=" * 80 + "\n\n")
        
        strategies = plan.get("strategies", {})
        for field, strategy in strategies.items():
            f.write(f"Field: {field}\n")
            f.write(f"  Method: {strategy.get('method', 'unknown')}\n")
            f.write(f"  Selector: {strategy.get('selector', 'none')}\n")
            
            result = extracted_data.get(field, "NOT IN RESULTS")
            if result is None:
                f.write(f"  Result: ❌ NOT FOUND\n")
            elif result == "Error":
                f.write(f"  Result: ⚠️ EXTRACTION ERROR\n")
            else:
                # Truncate long results
                result_str = str(result)
                if len(result_str) > 100:
                    result_str = result_str[:97] + "..."
                f.write(f"  Result: ✓ {result_str}\n")
            f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("VERIFICATION\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Completeness Score: {review.get('completeness_score', 'N/A')}\n")
        f.write(f"Summary: {review.get('summary', 'No summary')}\n")
        if review.get("analysis"):
            f.write(f"Analysis: {review.get('analysis')}\n")
        if review.get("missing_critical_fields"):
            f.write(f"Missing Fields: {', '.join(review['missing_critical_fields'])}\n")
    
    # --- 3. GENERATE MARKDOWN REPORT ---
    md = []
    
    # Header
    md.append(f"# 🔍 Extraction Report: {original_stem}")
    md.append(f"**Processed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append("")
    
    # Cost/Cache Info
    if cache_hit:
        md.append("## 💰 Processing Info")
        md.append("**Status:** ✅ Cache Hit (Saved ~$0.10)")
        md.append(f"**Fingerprint:** `{fingerprint}`")
    else:
        md.append("## 💰 Processing Info")
        md.append("**Status:** 🆕 Full Analysis (New page structure)")
        md.append(f"**Fingerprint:** `{fingerprint}` *(saved for future use)*")
    md.append("")
    
    # Context
    md.append("## 📋 Page Context")
    md.append(f"**Domain:** {context.get('domain', 'Unknown')}")
    md.append(f"**Page Type:** {context.get('page_type', 'Unknown')}")
    md.append(f"**Completeness:** {review.get('completeness_score', 'N/A')}")
    md.append("")
    
    # Executive Summary
    md.append("## 📊 Executive Summary")
    md.append(f"> {review.get('summary', 'No summary available.')}")
    md.append("")
    
    if review.get("analysis"):
        md.append(f"**Analysis:** {review.get('analysis')}")
        md.append("")
    
    # Extracted Data Table
    md.append("## 📦 Extracted Data")
    md.append("")
    md.append("| Field | Value | Method | Selector |")
    md.append("|:------|:------|:-------|:---------|")
    
    strategies = plan.get("strategies", {})
    
    for key, value in extracted_data.items():
        # Get extraction method info
        strategy_info = strategies.get(key, {})
        method = strategy_info.get("method", "-")
        selector = strategy_info.get("selector", "-")
        
        # Format value for table
        clean_val = str(value).replace("\n", " ").replace("|", "/")
        
        if clean_val == "None":
            clean_val = "❌ Not Found"
        elif clean_val == "Error":
            clean_val = "⚠️ Error"
        
        # Truncate long values
        if len(clean_val) > 100:
            clean_val = clean_val[:97] + "..."
        
        # Truncate long selectors
        clean_selector = str(selector)
        if len(clean_selector) > 50:
            clean_selector = clean_selector[:47] + "..."
        
        md.append(f"| **{key}** | {clean_val} | `{method}` | `{clean_selector}` |")
    
    md.append("")
    
    # Missing fields warning
    if review.get("missing_critical_fields"):
        md.append("## ⚠️ Missing Critical Data")
        md.append("")
        for field in review["missing_critical_fields"]:
            md.append(f"* {field}")
        md.append("")
    
    # Footer with links
    md.append("---")
    md.append(f"*Full data: `{safe_name}.json` | Debug: `{safe_name}_DEBUG.txt`*")
    
    # Write markdown file
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    
    log_event(f"📄 Reports generated:")
    log_event(f"   - {output_md_path.name}")
    log_event(f"   - {output_json_path.name}")
    log_event(f"   - {debug_path.name}")