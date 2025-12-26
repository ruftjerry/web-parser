# Gemini Model Comparison Report
**Generated:** 2025-12-26 10:47:32
**Test File:** 2025-12-26_17：30：53.html

---

## Summary

| Metric | Gemini 2.0 Flash | Gemini 2.5 Flash | Winner |
|--------|------------------|------------------|--------|
| **Items Extracted** | 30 | 30 | Tie |
| **Total Fields** | 436 | 343 | 2.0 ✅ |
| **Populated Fields** | 436 | 343 | 2.0 ✅ |
| **Null/Missing Fields** | 0 | 0 | Tie |
| **Avg Fields/Item** | 14.5 | 11.4 | 2.0 ✅ |
| **Processing Time** | 29.1s | 42.7s | 2.0 ✅ |
| **Cost** | $0.0070 | $0.0339 | 2.0 ✅ ($0.0070 vs $0.0339) |
| **Cost Difference** | - | **+$0.0269** (382% more) | - |

---

## Quality Analysis

### Field Completeness
- **2.0 Flash:** 436/436 fields populated (100.0%)
- **2.5 Flash:** 343/343 fields populated (100.0%)

**Difference:** -93 more fields populated by 2.0 Flash

---

## Sample Item Comparison

### Item 1

| Field | 2.0 Flash | 2.5 Flash | Match? |
|-------|-----------|-----------|--------|
| availability | IN STOCK | 25+ IN STOCK | ❌ |
| average_rating | MISSING | 4.9 | ❌ |
| brand | Samsung | Samsung | ✅ |
| capacity | 2TB | MISSING | ❌ |
| current_price | MISSING | $229.99 | ❌ |
| form_factor | M.2 | MISSING | ❌ |
| image_url | MISSING | [BASE64_REMOVED] | ❌ |
| in_store_only | True | MISSING | ❌ |
| interface | PCIe Gen 4 x4 | MISSING | ❌ |
| number_of_reviews | MISSING | 1702 | ❌ |
| original_price | 269.99 | $269.99 | ❌ |
| price | 229.99 | MISSING | ❌ |
| product_name | Samsung 990 PRO 2TB Samsung V NAND 3-bit MLC PCIe ... | Samsung 990 PRO 2TB Samsung V NAND 3-bit MLC PCIe ... | ✅ |
| product_url | MISSING | https://www.microcenter.com/product/660429/samsung... | ❌ |
| rating | 4.9 | MISSING | ❌ |
| review_count | 1702 | MISSING | ❌ |
| savings | 40.0 | Save $40.00 | ❌ |
| sku | 516120 | 516120 | ✅ |
| stock_count | 25+ | MISSING | ❌ |
| store_availability | MISSING | at Santa Clara Store | ❌ |
| store_name | Santa Clara Store | MISSING | ❌ |


---

## Cost-Benefit Analysis

**Per-page cost difference:** $0.0269

**If processing 100 pages:**
- 2.0 Flash: $0.70
- 2.5 Flash: $3.39
- **Extra cost:** $2.69

**Quality improvement:** -93 more fields populated per page

**Is it worth it?**
- Cost per additional field: $0.0269

---

## Recommendation

💰 **Use Gemini 2.0 Flash** - No quality difference detected, save 382% on costs.
