import os
import re
import json
import shutil
import time
import random
import traceback
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import openai

# Optional PDF text extraction dependency:
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

# -----------------------------
# CONFIG
# -----------------------------
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
client = openai.OpenAI(api_key=API_KEY)

# Tuning
MAX_PAGE_TEXT_CHARS = 12000          # Context window safety
MAX_CLASSIFY_TEXT_CHARS = 8000       # Triage sample size
MAX_ITEMS_PER_PAGE = 25              # Cap extraction per page
MAX_WORKERS = 4                      # Conservative concurrency
MAX_RETRIES = 6
CONTEXT_WINDOW_CHARS = 500           # Overlap size for sliding window

# Folders
DEFAULT_ARCHIVE_FOLDER = "Processed_Archive"
DEFAULT_ERRORS_FOLDER = "Errors"

# -----------------------------
# HELPERS
# -----------------------------
def collapse_ws(s: str) -> str:
    return " ".join((s or "").split())

def safe_filename(s: str, max_len: int = 80) -> str:
    s = re.sub(r"[^\w\s-]", "", (s or "")).strip()
    s = re.sub(r"[-\s]+", "_", s)
    return (s[:max_len] if s else "Research_Result")

def sha1_text(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8", errors="ignore")).hexdigest()

def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M")

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def write_json(path: Path, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def write_text(path: Path, txt: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)

def extract_numeric_price(price_str: str) -> float:
    """Returns raw float price or 0.0."""
    if not price_str: 
        return 0.0
    match = re.search(r"[\d,]+(?:\.\d{2})?", price_str)
    if not match:
        return 0.0
    try:
        return float(match.group(0).replace(",", ""))
    except:
        return 0.0

def bucket_price(price_val: float) -> int:
    """Buckets price to nearest $10."""
    return int(round(price_val / 10) * 10)

def normalize_name(n: str) -> str:
    n = collapse_ws((n or "").lower())
    n = re.sub(r"\b(pair|set|lot|for|sale)\b", "", n)
    return re.sub(r"[^a-z0-9]+", "", n)

# --- Attribute Normalization ---
ALIAS_MAP = {
    "shipping": ["delivery", "postage", "ship_cost", "freight"],
    "seller": ["vendor", "store", "sold_by", "merchant"],
    "location": ["city", "area", "region", "state", "zip"],
    "condition": ["grade", "quality", "state"],
    "sku": ["item_number", "id", "part_number", "model_number"]
}

def normalize_attributes(item: Dict[str, Any]) -> Dict[str, Any]:
    """Standardizes keys in the attributes dict."""
    raw_attrs = item.get("attributes", {})
    clean_attrs = {}
    
    # 1. Map aliases
    for k, v in raw_attrs.items():
        k_lower = k.lower().strip()
        mapped_key = k_lower
        
        # Check alias map
        for standard, aliases in ALIAS_MAP.items():
            if k_lower == standard or any(a in k_lower for a in aliases):
                mapped_key = standard
                break
        
        # Keep the value, just swap key
        clean_attrs[mapped_key] = v

    item["attributes"] = clean_attrs
    return item

# --- Fingerprinting ---
def item_fingerprint(it: Dict[str, Any]) -> str:
    """
    Robust fingerprinting. Prioritizes HARD IDs (SKU/URL).
    Falls back to fuzzy Name+Price+Seller.
    """
    attrs = it.get("attributes", {})
    
    # 1. Hard Identifier Check
    # Look for specific strong ID keys
    for key in ["sku", "url", "listing_id", "item_id"]:
        if val := attrs.get(key):
            # If found, this is the fingerprint (very safe)
            return sha1_text(f"{key}:{val}")

    # 2. Fuzzy Fallback
    name = normalize_name(it.get("name", ""))
    price_val = extract_numeric_price(it.get("price", ""))
    price_bucket = bucket_price(price_val)
    
    seller = normalize_name(str(attrs.get("seller", "")))
    location = normalize_name(str(attrs.get("location", "")))
    
    base = f"{name}|{price_bucket}|{seller}|{location}"
    return sha1_text(base)

# -----------------------------
# PDF ENGINE (Sliding Window)
# -----------------------------
def pdf_page_texts(pdf_path: Path) -> List[Tuple[str, str, str]]:
    """
    Returns list of (text, prev_tail, next_head) tuples.
    """
    if not HAS_PYMUPDF:
        raise RuntimeError("PyMuPDF not installed. Run: pip install pymupdf")
    
    doc = fitz.open(str(pdf_path))
    raw_pages = []
    
    # 1. Extract Raw Text
    for i in range(doc.page_count):
        text = collapse_ws(doc.load_page(i).get_text("text") or "")
        raw_pages.append(text)
    doc.close()
    
    # 2. Build Sliding Windows
    # prev_tail: last N chars of page i-1
    # next_head: first N chars of page i+1
    windowed_pages = []
    
    for i, text in enumerate(raw_pages):
        prev_tail = ""
        if i > 0:
            prev_txt = raw_pages[i-1]
            prev_tail = prev_txt[-CONTEXT_WINDOW_CHARS:] if len(prev_txt) > CONTEXT_WINDOW_CHARS else prev_txt
            
        next_head = ""
        if i < len(raw_pages) - 1:
            next_txt = raw_pages[i+1]
            next_head = next_txt[:CONTEXT_WINDOW_CHARS]
            
        windowed_pages.append((text, prev_tail, next_head))
        
    return windowed_pages

# -----------------------------
# LLM ENGINE
# -----------------------------
def llm_json(system: str, user_obj: Dict[str, Any]) -> Dict[str, Any]:
    payload = json.dumps(user_obj, ensure_ascii=False)
    
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                sleep_s = 2 * (2 ** attempt) + random.random()
                time.sleep(sleep_s)
            
            resp = client.chat.completions.create(
                model=MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": payload},
                ],
                timeout=90.0
            )
            return json.loads(resp.choices[0].message.content)
        
        except Exception as e:
            print(f"⚠️ LLM Warning (Attempt {attempt+1}): {e}")
            if attempt == MAX_RETRIES - 1:
                raise

# --- Phase 1: Triage ---
def classify_document(page1_text: str, file_name: str) -> Dict[str, Any]:
    system = "You are a document triage expert. Return valid JSON."
    user = {
        "task": "Analyze this document to guide extraction.",
        "input": {"file_name": file_name, "text_sample": page1_text[:MAX_CLASSIFY_TEXT_CHARS]},
        "output_schema": {
            "doc_type": "product_list | single_product | invoice | other",
            "domain": "audio | computer | photo | general",
            "description": "short_snake_case_name_for_filename",
            "primary_entity": "The main product or category being sold",
            "search_anchors": ["list of 3-5 keywords to help find relevant items"],
            "extraction_mode": "list (many items) OR detail (one main item)",
        }
    }
    return llm_json(system, user)

# --- Phase 2: Extraction ---
def extract_page_items(
    text_tuple: Tuple[str, str, str], 
    context: Dict[str, Any]
) -> Dict[str, Any]:
    
    main_text, prev_tail, next_head = text_tuple
    
    # Construct "Windowed" Context for LLM
    # We explicitly label the boundaries so the LLM knows what is "current"
    llm_input_text = f"""
    [PREVIOUS_PAGE_TAIL]
    {prev_tail}
    [END_PREVIOUS]

    [CURRENT_PAGE_CONTENT]
    {main_text[:MAX_PAGE_TEXT_CHARS]}
    [END_CURRENT]

    [NEXT_PAGE_HEAD]
    {next_head}
    [END_NEXT]
    """

    mode = context.get("extraction_mode", "list")
    entity = context.get("primary_entity", "General")

    system = "You are a flexible data extractor. Return JSON."
    
    # Mode-Specific Instructions
    if mode == "detail":
        instructions = [
            f"This is a DETAIL page for '{entity}'. Extract the MAIN product as the first item.",
            "Capture extensive specs, shipping, condition, and seller info for the main product.",
            "If other products appear (recommendations, related items), extract them but tag attribute 'is_related': true."
        ]
    else:
        instructions = [
            f"This is a LIST page. Extract rows of items matching '{entity}'.",
            "Use the [PREVIOUS/NEXT] context to repair split items (e.g. name on p1, price on p2).",
            "Only extract items that primarily belong to [CURRENT_PAGE_CONTENT]. Do not duplicate items fully in prev/next chunks."
        ]
    
    instructions.append("Extract 'name' and 'price'. Put ALL other details into 'attributes'.")

    user = {
        "task": "Extract items.",
        "context": context,
        "instructions": instructions,
        "output_schema": {
            "items": [
                {
                    "name": "string",
                    "price": "string",
                    "attributes": {"key": "value"}
                }
            ]
        },
        "page_text": llm_input_text
    }
    return llm_json(system, user)

# --- Phase 3: Filter & Tag ---
def filter_and_tag_items(items: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not items: return []
    
    # First: Normalize Attributes (Deterministic)
    normalized_items = [normalize_attributes(it) for it in items]
    
    system = "You are a data quality auditor. Return JSON."
    simplified_items = []
    
    # Broad relevance keys for the filter context
    relevance_keys = [
        "condition", "status", "category", "type", 
        "location", "posted", "date", "seller", 
        "brand", "model", "watt", "channel", "ohm",
        "shipping", "return", "tested", "working", "power", "sku", "is_related"
    ]
    
    for i, it in enumerate(normalized_items):
        attrs = it.get("attributes", {})
        hints = []
        for k, v in attrs.items():
            if any(r in k.lower() for r in relevance_keys):
                hints.append(f"{k}:{v}")
        
        simplified_items.append({
            "id": i, 
            "name": it.get("name", "Unknown"), 
            "price": it.get("price", ""),
            "context": ", ".join(hints)[:250]
        })

    user = {
        "task": "Review items. Mark 'noise' to delete. Tag 'accessories', 'parts', or 'related'.",
        "primary_entity": context.get("primary_entity", "General"),
        "items": simplified_items,
        "instructions": [
            "ids_to_drop: purely irrelevant items (ads, navigation links).",
            "ids_accessory: remotes, cables, stands (unless searching for them).",
            "ids_parts: 'parts only', 'broken', 'repair'.",
            "ids_related: suggestions/sponsored items that aren't the main result.",
            "If UNSURE, KEEP IT."
        ],
        "output_schema": {
            "ids_to_drop": [],
            "ids_accessory": [],
            "ids_parts": [],
            "ids_related": []
        }
    }
    
    result = llm_json(system, user)
    
    drop_ids = set(result.get("ids_to_drop", []))
    
    final_items = []
    for i, item in enumerate(normalized_items):
        if i in drop_ids:
            continue
        
        attrs = item["attributes"]
        if i in result.get("ids_accessory", []): attrs["is_accessory"] = True
        if i in result.get("ids_parts", []): attrs["is_parts_only"] = True
        if i in result.get("ids_related", []): attrs["is_related"] = True
            
        final_items.append(item)
        
    return final_items

# --- Phase 4: Summary with Fallback ---
def summarize_doc(doc_meta: Dict[str, Any], items: List[Dict[str, Any]]) -> List[str]:
    # 1. Try LLM Summary
    try:
        system = "You are a research analyst. Return JSON."
        user = {
            "task": "Summarize these items for a research note.",
            "meta": doc_meta,
            "sample_items": items[:20], 
            "total_count": len(items),
            "output_schema": {"bullets": ["3-5 high level insights"]}
        }
        bullets = llm_json(system, user).get("bullets", [])
        if bullets:
            return bullets
    except:
        pass # Fallback if LLM fails

    # 2. Deterministic Fallback
    count = len(items)
    prices = [extract_numeric_price(it.get("price", "")) for it in items]
    prices = [p for p in prices if p > 0]
    
    summary = [f"Total Items Found: {count}"]
    if prices:
        avg = sum(prices) / len(prices)
        summary.append(f"Price Range: ${min(prices):.2f} - ${max(prices):.2f}")
        summary.append(f"Average Price: ${avg:.2f}")
    
    return summary

# -----------------------------
# RENDERER
# -----------------------------
def render_markdown(doc_meta: Dict[str, Any], items: List[Dict[str, Any]], summary: List[str]) -> str:
    timestamp = now_stamp()
    lines = [
        f"# {doc_meta.get('description', 'Research Report')}",
        f"**Source:** `{doc_meta.get('source_name')}` | **Date:** {timestamp}",
        f"**Domain:** {doc_meta.get('domain')} | **Items Found:** {len(items)}",
        "",
        "## Executive Summary"
    ]
    lines.extend([f"- {s}" for s in summary])
    lines.append("")
    
    lines.append("## Item Table")
    lines.append("| Name | Price | Key Details |")
    lines.append("| :--- | :--- | :--- |")
    
    for it in items:
        name = (it.get("name") or "Unknown").replace("|", " ")
        price = (it.get("price") or "N/A").replace("|", " ")
        
        attrs = dict(it.get("attributes", {}))
        details = []
        
        # Priority Tags
        if attrs.pop("is_parts_only", False): details.append("🔴 **PARTS ONLY**")
        if attrs.pop("is_accessory", False): details.append("🔵 **ACCESSORY**")
        if attrs.pop("is_related", False): details.append("⚪ **RELATED ITEM**")

        # Priority Fields (Normalized)
        for p_key in ["condition", "status", "location", "shipping", "seller", "stock", "sku"]:
            if p_key in attrs:
                val = attrs.pop(p_key)
                details.append(f"**{p_key}:** {val}")
        
        # Remaining attributes (Soft Cap)
        for i, (k, v) in enumerate(attrs.items()):
            if i > 8: 
                details.append(f"*...and {len(attrs)-8} more*")
                break
            if v and str(v).lower() != "unknown":
                details.append(f"**{k}:** {v}")
                
        detail_str = "<br>".join(details).replace("|", " ")
        lines.append(f"| **{name}** | {price} | {detail_str} |")
        
    return "\n".join(lines)

# -----------------------------
# MAIN PROCESSOR
# -----------------------------
class ResearchAssistant:
    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        self.base_archive = self.source_path.parent.parent / DEFAULT_ARCHIVE_FOLDER
        self.errors_dir = self.base_archive.parent / DEFAULT_ERRORS_FOLDER

    def process(self):
        print(f"🚀 Processing: {self.source_path.name}")
        
        try:
            if not is_pdf(self.source_path):
                print("⚠️ Skipping non-PDF file.")
                return

            # 1. Read PDF (Windowed)
            # Returns list of (text, prev, next)
            pages_data = pdf_page_texts(self.source_path)
            if not pages_data:
                raise ValueError("PDF text extraction failed or empty.")
            
            # Use raw text of page 1 for triage
            page1_raw = pages_data[0][0]

            # 2. Triage
            print("🧠 Classifying document...")
            triage = classify_document(page1_raw, self.source_path.name)
            doc_desc = safe_filename(triage.get("description", "Research"))
            
            print(f"   → Entity: {triage.get('primary_entity')} | Mode: {triage.get('extraction_mode')}")

            # 3. Extract (Parallel)
            print(f"⚡ Extracting {len(pages_data)} pages (Workers: {MAX_WORKERS})...")
            all_items = []
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
                # Page Gating: Check length of 'text' (index 0 of tuple)
                futures = {
                    exe.submit(extract_page_items, pg_tuple, {
                        "page_number": i+1,
                        "primary_entity": triage.get("primary_entity"),
                        "extraction_mode": triage.get("extraction_mode"),
                        "domain": triage.get("domain")
                    }): i 
                    for i, pg_tuple in enumerate(pages_data) if len(pg_tuple[0]) > 100
                }
                
                for fut in as_completed(futures):
                    try:
                        res = fut.result()
                        # Enforce Max Items Cap
                        page_items = res.get("items", [])[:MAX_ITEMS_PER_PAGE]
                        all_items.extend(page_items)
                    except Exception as e:
                        print(f"❌ Page error: {e}")

            # 4. Dedupe
            unique_items = []
            seen = set()
            # Normalize ALL items before dedupe to ensure consistent keys
            normalized_pre_dedupe = [normalize_attributes(it) for it in all_items]
            
            for it in normalized_pre_dedupe:
                fp = item_fingerprint(it)
                if fp not in seen:
                    seen.add(fp)
                    unique_items.append(it)
            
            print(f"   → Extracted {len(all_items)} raw items, {len(unique_items)} after dedupe.")

            # 5. Filter & Tag
            print("🧹 Filtering & Tagging...")
            clean_items = filter_and_tag_items(unique_items, triage)
            print(f"   → {len(clean_items)} items remain (tagged).")

            # 6. Summarize
            summary = summarize_doc(triage, clean_items)

            # 7. Safe Write
            timestamp = now_stamp()
            base_name = f"{timestamp}_{doc_desc}"
            ensure_dir(self.base_archive)
            
            json_path = self.base_archive / f"{base_name}_data.json"
            md_path = self.base_archive / f"{base_name}_report.md"
            pdf_path = self.base_archive / f"{base_name}_source.pdf"

            final_data = {
                "meta": triage,
                "summary": summary,
                "items": clean_items
            }
            write_json(json_path, final_data)
            
            md_content = render_markdown(triage | {"source_name": self.source_path.name}, clean_items, summary)
            write_text(md_path, md_content)
            
            shutil.copy(self.source_path, pdf_path)
            
            if json_path.exists() and md_path.exists() and pdf_path.exists():
                os.remove(self.source_path)
                print(f"✅ Success! Saved as {base_name}")
            else:
                print("❌ Verification failed! Source file NOT deleted.")

        except Exception as e:
            print(f"💥 Failed: {e}")
            ensure_dir(self.errors_dir)
            try:
                shutil.move(self.source_path, self.errors_dir / self.source_path.name)
                write_text(self.errors_dir / f"{self.source_path.name}_error.txt", str(traceback.format_exc()))
            except Exception:
                pass

def is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        ResearchAssistant(sys.argv[1]).process()