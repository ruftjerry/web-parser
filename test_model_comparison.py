"""
test_model_comparison.py - Compare Gemini 2.0 Flash vs 2.5 Flash extraction quality

Usage:
    python test_model_comparison.py <path_to_html_file>

Example:
    python test_model_comparison.py "Pi_Inbox/Processed_Archive/2025-12-26_17:30:53.html"
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Import your existing modules
import html_brief
import analyzer
import gemini_extractor
from config import PRICING


def extract_with_model(html_content: str, model_name: str, hypothesis: dict) -> dict:
    """
    Run extraction with a specific Gemini model.

    Returns:
        dict with keys: data, tokens_in, tokens_out, time_seconds, cost
    """
    print(f"\n{'='*60}")
    print(f"Testing {model_name}")
    print(f"{'='*60}")

    # Temporarily override the model in gemini_extractor
    import gemini_extractor as ge
    original_model = ge.MODEL_CONTEXT
    ge.MODEL_CONTEXT = model_name

    start_time = time.time()

    try:
        # Run extraction
        extracted_data = ge.extract_data(html_content, hypothesis)

        # Get token counts from the last API call
        # Note: This is a simplification - you'd need to capture actual usage
        # For now, we'll estimate based on content size
        tokens_in = len(html_content) // 4  # Rough estimate: 4 chars per token
        tokens_out = len(json.dumps(extracted_data)) // 4

        elapsed = time.time() - start_time

        # Calculate cost
        pricing = PRICING.get(model_name, {"input": 0, "output": 0})
        cost = ((tokens_in / 1_000_000) * pricing["input"]) + \
               ((tokens_out / 1_000_000) * pricing["output"])

        return {
            "data": extracted_data,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "time_seconds": elapsed,
            "cost": cost
        }

    finally:
        # Restore original model
        ge.MODEL_CONTEXT = original_model


def count_fields(items: list) -> dict:
    """Count populated vs null fields across all items."""
    if not items:
        return {"total_fields": 0, "populated": 0, "null": 0}

    total_fields = 0
    populated = 0
    null_count = 0

    for item in items:
        if isinstance(item, dict):
            for key, value in item.items():
                total_fields += 1
                if value is None or value == "" or value == "N/A":
                    null_count += 1
                else:
                    populated += 1

    return {
        "total_fields": total_fields,
        "populated": populated,
        "null": null_count,
        "avg_fields_per_item": total_fields / len(items) if items else 0
    }


def compare_extractions(result_2_0: dict, result_2_5: dict, filename: str) -> str:
    """Generate a markdown comparison report."""

    data_2_0 = result_2_0["data"]
    data_2_5 = result_2_5["data"]

    items_2_0 = data_2_0.get("items", [])
    items_2_5 = data_2_5.get("items", [])

    fields_2_0 = count_fields(items_2_0)
    fields_2_5 = count_fields(items_2_5)

    # Build report
    report = f"""# Gemini Model Comparison Report
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Test File:** {filename}

---

## Summary

| Metric | Gemini 2.0 Flash | Gemini 2.5 Flash | Winner |
|--------|------------------|------------------|--------|
| **Items Extracted** | {len(items_2_0)} | {len(items_2_5)} | {"Tie" if len(items_2_0) == len(items_2_5) else ("2.5 ✅" if len(items_2_5) > len(items_2_0) else "2.0 ✅")} |
| **Total Fields** | {fields_2_0['total_fields']} | {fields_2_5['total_fields']} | {"Tie" if fields_2_0['total_fields'] == fields_2_5['total_fields'] else ("2.5 ✅" if fields_2_5['total_fields'] > fields_2_0['total_fields'] else "2.0 ✅")} |
| **Populated Fields** | {fields_2_0['populated']} | {fields_2_5['populated']} | {"Tie" if fields_2_0['populated'] == fields_2_5['populated'] else ("2.5 ✅" if fields_2_5['populated'] > fields_2_0['populated'] else "2.0 ✅")} |
| **Null/Missing Fields** | {fields_2_0['null']} | {fields_2_5['null']} | {"Tie" if fields_2_0['null'] == fields_2_5['null'] else ("2.0 ✅" if fields_2_0['null'] < fields_2_5['null'] else "2.5 ✅")} |
| **Avg Fields/Item** | {fields_2_0['avg_fields_per_item']:.1f} | {fields_2_5['avg_fields_per_item']:.1f} | {"Tie" if abs(fields_2_0['avg_fields_per_item'] - fields_2_5['avg_fields_per_item']) < 0.1 else ("2.5 ✅" if fields_2_5['avg_fields_per_item'] > fields_2_0['avg_fields_per_item'] else "2.0 ✅")} |
| **Processing Time** | {result_2_0['time_seconds']:.1f}s | {result_2_5['time_seconds']:.1f}s | {"Tie" if abs(result_2_0['time_seconds'] - result_2_5['time_seconds']) < 2 else ("2.5 ✅" if result_2_5['time_seconds'] < result_2_0['time_seconds'] else "2.0 ✅")} |
| **Cost** | ${result_2_0['cost']:.4f} | ${result_2_5['cost']:.4f} | 2.0 ✅ (${result_2_0['cost']:.4f} vs ${result_2_5['cost']:.4f}) |
| **Cost Difference** | - | **+${result_2_5['cost'] - result_2_0['cost']:.4f}** ({((result_2_5['cost'] / result_2_0['cost'] - 1) * 100):.0f}% more) | - |

---

## Quality Analysis

### Field Completeness
- **2.0 Flash:** {fields_2_0['populated']}/{fields_2_0['total_fields']} fields populated ({(fields_2_0['populated']/fields_2_0['total_fields']*100):.1f}%)
- **2.5 Flash:** {fields_2_5['populated']}/{fields_2_5['total_fields']} fields populated ({(fields_2_5['populated']/fields_2_5['total_fields']*100):.1f}%)

**Difference:** {fields_2_5['populated'] - fields_2_0['populated']} more fields populated by {"2.5" if fields_2_5['populated'] > fields_2_0['populated'] else "2.0"} Flash

---

## Sample Item Comparison

### Item 1
"""

    # Compare first item from each
    if items_2_0 and items_2_5:
        item1_2_0 = items_2_0[0]
        item1_2_5 = items_2_5[0]

        # Get all unique keys
        all_keys = set(list(item1_2_0.keys()) + list(item1_2_5.keys()))

        report += "\n| Field | 2.0 Flash | 2.5 Flash | Match? |\n"
        report += "|-------|-----------|-----------|--------|\n"

        for key in sorted(all_keys):
            val_2_0 = item1_2_0.get(key, "MISSING")
            val_2_5 = item1_2_5.get(key, "MISSING")

            # Truncate long values
            val_2_0_str = str(val_2_0)[:50] + "..." if len(str(val_2_0)) > 50 else str(val_2_0)
            val_2_5_str = str(val_2_5)[:50] + "..." if len(str(val_2_5)) > 50 else str(val_2_5)

            match = "✅" if val_2_0 == val_2_5 else "❌"

            report += f"| {key} | {val_2_0_str} | {val_2_5_str} | {match} |\n"

    report += f"""

---

## Cost-Benefit Analysis

**Per-page cost difference:** ${result_2_5['cost'] - result_2_0['cost']:.4f}

**If processing 100 pages:**
- 2.0 Flash: ${result_2_0['cost'] * 100:.2f}
- 2.5 Flash: ${result_2_5['cost'] * 100:.2f}
- **Extra cost:** ${(result_2_5['cost'] - result_2_0['cost']) * 100:.2f}

**Quality improvement:** {fields_2_5['populated'] - fields_2_0['populated']} more fields populated per page

**Is it worth it?**
- Cost per additional field: ${(result_2_5['cost'] - result_2_0['cost']) / max(1, fields_2_5['populated'] - fields_2_0['populated']):.4f}

---

## Recommendation

"""

    # Generate recommendation
    quality_gain = fields_2_5['populated'] - fields_2_0['populated']
    cost_increase_pct = ((result_2_5['cost'] / result_2_0['cost'] - 1) * 100)

    if quality_gain > 5:
        report += f"✅ **Use Gemini 2.5 Flash** - Significantly better quality ({quality_gain} more fields) justifies {cost_increase_pct:.0f}% cost increase.\n"
    elif quality_gain > 0:
        report += f"⚖️ **Marginal improvement** - 2.5 Flash is slightly better (+{quality_gain} fields) but {cost_increase_pct:.0f}% more expensive. Your call.\n"
    else:
        report += f"💰 **Use Gemini 2.0 Flash** - No quality difference detected, save {cost_increase_pct:.0f}% on costs.\n"

    return report


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_model_comparison.py <path_to_html_file>")
        print("\nExample:")
        print('  python test_model_comparison.py "Pi_Inbox/Processed_Archive/2025-12-26_17:30:53.html"')
        sys.exit(1)

    html_path = Path(sys.argv[1])

    if not html_path.exists():
        print(f"❌ File not found: {html_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"GEMINI MODEL COMPARISON TEST")
    print(f"{'='*60}")
    print(f"File: {html_path.name}")
    print(f"Size: {html_path.stat().st_size / 1024:.1f} KB")

    # Step 1: Read and clean HTML
    print("\n📋 Step 1: Reading and cleaning HTML...")
    html_content = html_path.read_text(encoding='utf-8')
    brief = html_brief.create_brief(html_content)
    cleaned_html = brief.get('full_clean_html', '')
    print(f"   Cleaned: {len(html_content):,} → {len(cleaned_html):,} chars")

    # Step 2: Generate hypothesis (using same for both models)
    print("\n🔍 Step 2: Generating hypothesis...")
    html_sample = cleaned_html[:50000]
    hypothesis = analyzer.analyze_page(html_sample)
    print(f"   Page type: {hypothesis.get('page_type')}")
    print(f"   Source: {hypothesis.get('source')}")
    print(f"   Category: {hypothesis.get('category')}")
    print(f"   Item count: {hypothesis.get('item_count')}")

    # Step 3: Extract with both models
    print("\n⚡ Step 3: Running extractions...")

    result_2_0 = extract_with_model(cleaned_html, "gemini-2.0-flash", hypothesis)
    print(f"   ✅ 2.0 Flash: {len(result_2_0['data'].get('items', []))} items, ${result_2_0['cost']:.4f}, {result_2_0['time_seconds']:.1f}s")

    result_2_5 = extract_with_model(cleaned_html, "gemini-2.5-flash", hypothesis)
    print(f"   ✅ 2.5 Flash: {len(result_2_5['data'].get('items', []))} items, ${result_2_5['cost']:.4f}, {result_2_5['time_seconds']:.1f}s")

    # Step 4: Generate comparison report
    print("\n📊 Step 4: Generating comparison report...")

    output_dir = Path("test_results")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    test_dir = output_dir / f"{timestamp}_{html_path.stem}"
    test_dir.mkdir(exist_ok=True)

    # Save individual results
    (test_dir / "gemini-2.0-flash_extraction.json").write_text(
        json.dumps(result_2_0["data"], indent=2, ensure_ascii=False)
    )
    (test_dir / "gemini-2.5-flash_extraction.json").write_text(
        json.dumps(result_2_5["data"], indent=2, ensure_ascii=False)
    )

    # Save comparison report
    report = compare_extractions(result_2_0, result_2_5, html_path.name)
    report_path = test_dir / "comparison_report.md"
    report_path.write_text(report)

    print(f"\n✅ Test complete!")
    print(f"\n📁 Results saved to: {test_dir}")
    print(f"   - gemini-2.0-flash_extraction.json")
    print(f"   - gemini-2.5-flash_extraction.json")
    print(f"   - comparison_report.md")

    print("\n" + "="*60)
    print("COMPARISON REPORT")
    print("="*60)
    print(report)


if __name__ == "__main__":
    main()
