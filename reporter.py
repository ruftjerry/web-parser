"""
reporter.py - Generates output files from formatted data and validation results
"""

import json
from pathlib import Path
from datetime import datetime
from config import OUTPUT_DIR
from utils_logging import log_event

def generate_reports(
    hypothesis: dict,
    extracted_data: dict,
    formatted_markdown: str,
    validation_result: dict,
    original_filename: str
) -> tuple:
    """
    Generate Markdown, JSON, and DEBUG output files.
    
    Returns:
        tuple: (md_path, json_path, debug_path)
    """
    log_event("📊 Step 4: Generating Reports...")
    
    # Create timestamp-based filename
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    base_name = Path(original_filename).stem
    safe_name = base_name.replace(" ", "_").replace(":", "-")
    
    status = validation_result.get('status', 'unknown')
    
    # Determine file suffix based on status
    if status == 'success':
        suffix = ""
    elif status == 'extraction_incomplete':
        suffix = "_INCOMPLETE"
    else:
        suffix = "_FAILED"
    
    md_filename = f"{timestamp}_{safe_name}{suffix}.md"
    json_filename = f"{timestamp}_{safe_name}{suffix}.json"
    debug_filename = f"{timestamp}_{safe_name}_DEBUG.json"
    
    md_path = OUTPUT_DIR / md_filename
    json_path = OUTPUT_DIR / json_filename
    debug_path = OUTPUT_DIR / debug_filename
    
    # Generate Markdown report
    md_content = generate_markdown(
        hypothesis, 
        formatted_markdown, 
        validation_result, 
        original_filename, 
        timestamp
    )
    md_path.write_text(md_content, encoding='utf-8')
    
    # Generate JSON output
    json_content = generate_json_output(
        hypothesis, 
        extracted_data, 
        validation_result, 
        original_filename, 
        timestamp
    )
    json_path.write_text(json.dumps(json_content, indent=2, ensure_ascii=False), encoding='utf-8')
    
    # Generate DEBUG file (full diagnostic info)
    debug_content = {
        "timestamp": timestamp,
        "original_file": original_filename,
        "hypothesis": hypothesis,
        "extracted_data": extracted_data,
        "formatted_markdown_length": len(formatted_markdown),
        "validation_result": validation_result
    }
    debug_path.write_text(json.dumps(debug_content, indent=2, ensure_ascii=False), encoding='utf-8')
    
    log_event(f"   📄 Generated reports:")
    log_event(f"      - {md_filename}")
    log_event(f"      - {json_filename}")
    log_event(f"      - {debug_filename}")
    
    return (md_path, json_path, debug_path)


def generate_markdown(hypothesis: dict, formatted_markdown: str, validation_result: dict, 
                     original_filename: str, timestamp: str) -> str:
    """Generate a beautiful Markdown report by combining insights with formatted data."""
    
    status = validation_result.get('status', 'unknown')
    
    if status == 'success':
        return generate_success_markdown(hypothesis, formatted_markdown, validation_result, original_filename, timestamp)
    else:
        return generate_failure_markdown(hypothesis, formatted_markdown, validation_result, original_filename, timestamp)


def generate_success_markdown(hypothesis: dict, formatted_markdown: str, validation_result: dict,
                              original_filename: str, timestamp: str) -> str:
    """Generate Markdown for successful extraction."""
    
    insights = validation_result.get('insights', {})
    statistics = validation_result.get('statistics', {})
    validation = validation_result.get('validation', {})
    
    exec_summary = insights.get('executive_summary', 'Data extracted successfully.')
    key_findings = insights.get('key_findings', '')
    recommendation = insights.get('recommendation', '')
    
    total_items = statistics.get('total_items', 'Unknown')
    key_metrics = statistics.get('key_metrics', '')
    
    data_quality = validation.get('data_quality', 'Unknown')
    
    md = f"""# 📊 Extraction Report: {original_filename}
**Processed:** {timestamp}

## ✅ Status: SUCCESS

### 🔍 Page Analysis
**Type:** {hypothesis.get('page_type', 'Unknown')}  
**Source:** {hypothesis.get('source', 'Unknown')}  
**Category:** {hypothesis.get('category', 'Unknown')}  
**Items Found:** {total_items}

### 💡 Executive Summary
{exec_summary}

"""

    if key_findings:
        md += f"""### 🎯 Key Findings
{key_findings}

"""

    if key_metrics:
        md += f"""### 📈 Statistics
{key_metrics}

"""

    # Insert the formatted data from formatter.py
    md += f"""---

{formatted_markdown}

---

"""

    if recommendation:
        md += f"""### 💭 Recommendation
{recommendation}

"""

    md += f"""### ✅ Validation
**Data Quality:** {data_quality}  
**Completeness:** {validation.get('completeness', 'Complete')}

---
*Full JSON data: `{timestamp}_{Path(original_filename).stem}.json`*  
*Debug info: `{timestamp}_{Path(original_filename).stem}_DEBUG.json`*
"""

    return md


def generate_failure_markdown(hypothesis: dict, formatted_markdown: str, validation_result: dict,
                              original_filename: str, timestamp: str) -> str:
    """Generate Markdown for failed/incomplete extraction."""
    
    validation = validation_result.get('validation', {})
    user_message = validation_result.get('user_message', 'Extraction failed.')
    partial_insights = validation_result.get('partial_insights', {})
    
    problem = validation.get('problem', 'Unknown issue')
    expected = validation.get('expected_items', 'Unknown')
    actual = validation.get('actual_items', 'Unknown')
    
    partial_summary = partial_insights.get('summary', '')
    
    md = f"""# ⚠️ Extraction Report: {original_filename}
**Processed:** {timestamp}

## ❌ Status: EXTRACTION ISSUE

### 🔍 Page Analysis (Hypothesis)
**Type:** {hypothesis.get('page_type', 'Unknown')}  
**Source:** {hypothesis.get('source', 'Unknown')}  
**Category:** {hypothesis.get('category', 'Unknown')}  
**Expected Items:** {expected}

### ⚠️ What Went Wrong
{user_message}

**Problem:** {problem}  
**Expected:** {expected} items  
**Actually Got:** {actual} items

"""

    if partial_summary:
        md += f"""### 📦 Partial Results
{partial_summary}

"""

    if formatted_markdown and len(formatted_markdown) > 50:
        md += f"""### 📋 Partial Data Extracted
{formatted_markdown}

"""

    md += f"""### 🔧 Next Steps
1. Review the DEBUG file to see what was extracted
2. Check if the HTML file is complete and well-formed
3. Try re-processing the file
4. If issue persists, this page type may need special handling

---
*Partial data: `{timestamp}_{Path(original_filename).stem}_FAILED.json`*  
*Debug info: `{timestamp}_{Path(original_filename).stem}_DEBUG.json`*
"""

    return md


def generate_json_output(hypothesis: dict, extracted_data: dict, validation_result: dict,
                        original_filename: str, timestamp: str) -> dict:
    """Generate structured JSON output."""
    
    status = validation_result.get('status', 'unknown')
    
    output = {
        "meta": {
            "timestamp": timestamp,
            "original_file": original_filename,
            "status": status,
            "page_type": hypothesis.get('page_type', 'Unknown'),
            "source": hypothesis.get('source', 'Unknown'),
            "category": hypothesis.get('category', 'Unknown')
        },
        "hypothesis": hypothesis,
        "extracted_data": extracted_data,
        "validation": validation_result.get('validation', {})
    }
    
    if status == 'success':
        output["insights"] = validation_result.get('insights', {})
        output["statistics"] = validation_result.get('statistics', {})
    else:
        output["issue"] = validation_result.get('user_message', 'Extraction failed')
        output["partial_insights"] = validation_result.get('partial_insights', {})
    
    return output