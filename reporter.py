"""
reporter.py - Generates output files from formatted data and validation results
"""

import json
import re
from pathlib import Path
from datetime import datetime
from config import OUTPUT_DIR
from utils_logging import log_event
from collections import Counter


def analyze_list_items(items: list) -> dict:
    """
    Analyze items in a list to find dominant patterns.
    
    Returns dict with:
        - dominant_model: Most common brand+model combo (if 50%+ match)
        - dominant_brand: Most common brand (if 50%+ match) 
        - dominant_attributes: Dict of most common attributes
    """
    if not items or len(items) < 2:
        return {}
    
    brands = []
    models = []
    brand_model_combos = []
    attributes = {}
    
    for item in items:
        if not isinstance(item, dict):
            continue
        
        # Extract brand
        brand = item.get('brand', '').strip()
        if brand:
            brands.append(brand)
        
        # Extract model/product name and try to parse model from it
        product_name = (item.get('product_name') or 
                       item.get('title') or 
                       item.get('name', '')).strip()
        
        # Try to extract model (usually first 2-3 words after brand)
        if product_name and brand:
            # Remove brand from product name and take next 1-2 significant words
            name_without_brand = product_name.replace(brand, '').strip()
            words = [w for w in name_without_brand.split() if len(w) > 1][:2]
            if words:
                model = ' '.join(words)
                models.append(model)
                brand_model_combos.append(f"{brand} {model}")
        
        # Extract common attributes
        for key in ['capacity', 'size', 'color', 'condition', 'type']:
            value = item.get(key, '').strip()
            if value:
                if key not in attributes:
                    attributes[key] = []
                attributes[key].append(value)
    
    total_items = len(items)
    result = {}
    
    # Check for dominant brand+model (50%+ threshold)
    if brand_model_combos:
        combo_counts = Counter(brand_model_combos)
        most_common_combo, combo_count = combo_counts.most_common(1)[0]
        if combo_count / total_items >= 0.5:
            result['dominant_model'] = most_common_combo
    
    # Check for dominant brand (50%+ threshold)
    if brands:
        brand_counts = Counter(brands)
        most_common_brand, brand_count = brand_counts.most_common(1)[0]
        if brand_count / total_items >= 0.5:
            result['dominant_brand'] = most_common_brand
    
    # Find most common attribute for each type
    result['dominant_attributes'] = {}
    for attr_name, attr_values in attributes.items():
        if attr_values:
            attr_counts = Counter(attr_values)
            most_common_attr, attr_count = attr_counts.most_common(1)[0]
            if attr_count / total_items >= 0.3:  # Lower threshold for attributes
                result['dominant_attributes'][attr_name] = most_common_attr
    
    return result


def generate_smart_filename(
    hypothesis: dict, 
    extracted_data: dict, 
    timestamp: str
) -> str:
    """
    Generate semantic filename from extraction context.
    Format: YYYYMMDD-HHMM-Source-Product-Type
    
    Args:
        hypothesis: Page analysis hypothesis dict
        extracted_data: Extracted data dict
        timestamp: Timestamp string (YYYYMMDD-HHMM format)
    
    Returns:
        Base filename string (without extension)
    """
    # Extract and sanitize source (max 20 chars)
    source = hypothesis.get('source', 'Unknown')
    source = re.sub(r'[^a-zA-Z0-9]', '', source)  # Remove special chars
    if not source:
        source = 'Unknown'
    source = source[:20].capitalize()
    
    # Determine page type: single, list, or auction
    page_type_raw = hypothesis.get('page_type', '').lower()
    item_count_raw = str(hypothesis.get('item_count', '')).lower()
    
    # Parse item_count - handle both integers and strings like "multiple (estimate 30)"
    item_count = 0
    is_multiple = False
    
    if 'multiple' in item_count_raw or 'many' in item_count_raw:
        is_multiple = True
    else:
        # Try to extract numeric value
        try:
            # Extract first number from string
            numbers = re.findall(r'\d+', item_count_raw)
            if numbers:
                item_count = int(numbers[0])
            else:
                item_count = int(item_count_raw) if item_count_raw else 0
        except (ValueError, TypeError):
            item_count = 0
    
    # Classify page type with better pattern matching
    if 'auction' in page_type_raw or 'bid' in page_type_raw:
        page_type = 'auction'
    elif item_count == 1 or ('single' in page_type_raw or 'product' in page_type_raw and not is_multiple):
        page_type = 'single'
    elif (is_multiple or item_count > 1 or 
          'list' in page_type_raw or 'catalog' in page_type_raw or 
          'search' in page_type_raw or 'results' in page_type_raw):
        page_type = 'list'
    else:
        page_type = 'unknown'
    
    # Extract product name based on page type
    product = 'Unknown'
    
    if page_type == 'single':
        # Try to get from extracted_data['items'][0]['title'] or similar
        items = extracted_data.get('items', [])
        if items and isinstance(items, list) and len(items) > 0:
            first_item = items[0]
            if isinstance(first_item, dict):
                # Try common title field names
                product = (first_item.get('title') or 
                          first_item.get('name') or 
                          first_item.get('product_name') or 
                          'Unknown')
        
        # Take first 2-3 words, sanitize, max 30 chars
        if product and product != 'Unknown':
            words = product.split()[:3]  # First 3 words max
            product = ' '.join(words)
            product = re.sub(r'[^a-zA-Z0-9\s]', '', product)  # Remove special chars
            product = product.replace(' ', '-')  # Replace spaces with hyphens
            product = product[:30]  # Max 30 chars
    
    elif page_type == 'list' or page_type == 'auction':
        # IMPROVED: Analyze items to find dominant pattern
        items = extracted_data.get('items', [])
        
        if items and len(items) >= 2:
            analysis = analyze_list_items(items)
            
            # Priority 1: Dominant model (brand + model, 50%+ of items)
            if 'dominant_model' in analysis:
                product = analysis['dominant_model']
                product = re.sub(r'[^a-zA-Z0-9\s]', '', product)
                product = product.replace(' ', '')[:30]  # No hyphens for brand+model
            
            # Priority 2: Dominant brand + most common attribute  
            elif 'dominant_brand' in analysis and analysis.get('dominant_attributes'):
                brand = analysis['dominant_brand']
                # Get first available attribute (capacity, size, etc.)
                attrs = analysis['dominant_attributes']
                attr_value = next(iter(attrs.values()))
                product = f"{brand}{attr_value}"
                product = re.sub(r'[^a-zA-Z0-9\s]', '', product)
                product = product.replace(' ', '')[:30]
            
            # Priority 3: Dominant attribute + category
            elif analysis.get('dominant_attributes'):
                attrs = analysis['dominant_attributes']
                attr_value = next(iter(attrs.values()))
                category_short = hypothesis.get('category', '').split()[0]  # First word of category
                product = f"{attr_value}{category_short}"
                product = re.sub(r'[^a-zA-Z0-9\s]', '', product)
                product = product.replace(' ', '')[:30]
            
            # Priority 4: Fallback to category from hypothesis
            else:
                product = hypothesis.get('category', 'Unknown')
                if product and product != 'Unknown':
                    product = re.sub(r'[^a-zA-Z0-9\s]', '', product)
                    product = product.replace(' ', '-')
                    product = product[:30]
        else:
            # Single item in a "list" or no items - use category
            product = hypothesis.get('category', 'Unknown')
            if product and product != 'Unknown':
                product = re.sub(r'[^a-zA-Z0-9\s]', '', product)
                product = product.replace(' ', '-')
                product = product[:30]
    
    # Fallback: try category even if page_type is unknown
    if not product or product == 'Unknown':
        category = hypothesis.get('category', '')
        if category:
            product = re.sub(r'[^a-zA-Z0-9\s]', '', category)
            product = product.replace(' ', '-')
            product = product[:30] if product else 'Unknown'
        else:
            product = 'Unknown'
    
    # Assemble filename: {timestamp}-{source}-{product}-{type}
    # Ensure total length ≤ 100 chars (timestamp is ~13 chars, so ~87 for rest)
    # Priority: timestamp (fixed) > source (20) > type (7) > product (truncate if needed)
    base_parts = [timestamp, source, product, page_type]
    base_name = '-'.join(base_parts)
    
    # Calculate available space (100 - timestamp - separators)
    # timestamp (~13) + 3 separators = ~16, so ~84 for content
    max_content_length = 100 - len(timestamp) - 3  # 3 separators
    
    if len(base_name) > 100:
        # Truncate product name to fit
        available_for_product = max_content_length - len(source) - len(page_type) - 2  # 2 separators
        if available_for_product > 0:
            product = product[:available_for_product]
            base_name = f"{timestamp}-{source}-{product}-{page_type}"
        else:
            # Fallback: just use timestamp-source-type
            base_name = f"{timestamp}-{source}-{page_type}"
    
    return base_name


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
    base_name = generate_smart_filename(hypothesis, extracted_data, timestamp)
    
    status = validation_result.get('status', 'unknown')
    
    # Determine file suffix based on status
    if status == 'success':
        suffix = ""
    elif status == 'extraction_incomplete':
        suffix = "_INCOMPLETE"
    else:
        suffix = "_FAILED"
    
    md_filename = f"{base_name}{suffix}.md"
    json_filename = f"{base_name}{suffix}.json"
    debug_filename = f"{base_name}_DEBUG.json"
    
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
