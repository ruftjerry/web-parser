import os
import re
import json
import shutil
import time
import random
import traceback
import hashlib
import csv
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------
# DEPENDENCIES
# -----------------------------
try:
    import openai
    from openai import RateLimitError, APITimeoutError, APIConnectionError
except ImportError:
    print("❌ Missing dependency: pip install openai")
    exit(1)

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# -----------------------------
# CONFIG & MODELS
# -----------------------------
API_KEY = os.getenv("OPENAI_API_KEY")

_thread_local = threading.local()
_log_lock = threading.Lock()

MODEL_SMART = "gpt-4o"       # Strategy, Triage, Summary
MODEL_FAST = "gpt-4o-mini"   # Extraction, Filtering

PRICING = {
    "gpt-4o":      {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60}
}

TOKEN_LOG_FILE = "token_usage_log.csv"

# Tuning
MAX_PAGE_TEXT_CHARS = 12000
MAX_ITEMS_PER_PAGE = 25
MAX_WORKERS = 4
MAX_RETRIES = 6
CONTEXT_WINDOW_CHARS = 500

DEFAULT_ARCHIVE_FOLDER = "Processed_Archive"
DEFAULT_ERRORS_FOLDER = "Errors"

# -----------------------------
# LOGGING SETUP
# -----------------------------
def setup_logging(source_path: Path) -> logging.Logger:
    log_dir = source_path.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Use hash of full path to ensure uniqueness across runs
    logger_name = f"research_{hashlib.md5(str(source_path).encode()).hexdigest()[:8]}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # Changed to DEBUG to capture dedup details
    
    # File Handler
    fh = logging.FileHandler(log_dir / f"{source_path.stem}.log", encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s [%(threadName)s] %(levelname)s: %(message)s'))
    
    # Stream Handler (Minimal output to console to play nice with tqdm)
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)  # Only INFO and above to console
    sh.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.addHandler(fh)
    # Only add stream handler if tqdm isn't managing stdout
    if not HAS_TQDM:
        logger.addHandler(sh)
        
    return logger

# -----------------------------
# HELPERS
# -----------------------------
def get_client():
    if not hasattr(_thread_local, "client"):
        _thread_local.client = openai.OpenAI(api_key=API_KEY)
    return _thread_local.client

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

# --- Currency & Price Logic ---
CURRENCY_MAP = {
    'USD': r'\$|USD|dollars',
    'EUR': r'€|EUR|euros',
    'GBP': r'£|GBP|pounds',
    'JPY': r'¥|JPY|yen'
}

def extract_price_info(price_str: str) -> Dict[str, Any]:
    if not price_str: 
        return {"value": 0.0, "currency": "USD", "raw": ""}
        
    # Heuristic: Remove common non-digit price words
    clean = re.sub(r"(?i)(sold|ask|bid|for|only|winning|offer|price|approx)", "", str(price_str))
    
    # Detect Currency
    currency = "USD" # Default
    for code, pattern in CURRENCY_MAP.items():
        if re.search(pattern, price_str, re.IGNORECASE):
            currency = code
            break
            
    # Extract Value
    match = re.search(r"[\d,]+(?:\.\d{2})?", clean)
    val = 0.0
    if match:
        try:
            val = float(match.group(0).replace(",", ""))
        except:
            pass
            
    return {"value": val, "currency": currency, "raw": price_str}

def calculate_landed_cost(price_val: float, shipping_str: str) -> float:
    """Returns total cost (Price + Shipping). Returns 0.0 if calc fails."""
    if not shipping_str: return 0.0
    
    shipping_str = shipping_str.lower()
    if "free" in shipping_str:
        return price_val
        
    ship_info = extract_price_info(shipping_str)
    if ship_info["value"] > 0:
        return price_val + ship_info["value"]
    
    return 0.0

def bucket_price(price_val: float) -> int:
    return int(round(price_val / 10) * 10)

def normalize_name(n: str) -> str:
    n = collapse_ws((n or "").lower())
    n = re.sub(r"\b(pair|set|lot|for|sale)\b", "", n)
    return re.sub(r"[^a-z0-9]+", "", n)

def parse_iso_date(date_str: str, anchor_year: Optional[int] = None) -> Tuple[Optional[str], bool]:
    if not date_str: return None, False
    clean = re.sub(r"(?i)^(sold|ended|listed|posted|on|date)[:\s]+", "", date_str).strip()
    
    formats_with_year = [
        "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", 
        "%m/%d/%Y", "%m/%d/%y", "%d %b %Y"
    ]
    for fmt in formats_with_year:
        try:
            dt = datetime.strptime(clean, fmt)
            return dt.strftime("%Y-%m-%d"), False
        except ValueError:
            continue
            
    formats_no_year = ["%b %d", "%B %d", "%m/%d"]
    year_to_use = anchor_year if anchor_year else datetime.now().year
    is_inferred = (anchor_year is None) 

    for fmt in formats_no_year:
        try:
            dt = datetime.strptime(clean, fmt)
            dt = dt.replace(year=year_to_use)
            return dt.strftime("%Y-%m-%d"), is_inferred
        except ValueError:
            continue

    return None, False

def log_token_usage(model: str, usage_obj: Any, task_type: str):
    file_exists = os.path.isfile(TOKEN_LOG_FILE)
    in_tokens = usage_obj.prompt_tokens
    out_tokens = usage_obj.completion_tokens
    total = usage_obj.total_tokens
    
    rates = PRICING.get(model, {"input": 0, "output": 0})
    cost = (in_tokens / 1_000_000 * rates["input"]) + (out_tokens / 1_000_000 * rates["output"])
    
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task": task_type,
        "model": model,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "total_tokens": total,
        "estimated_cost_usd": round(cost, 6)
    }
    
    try:
        with _log_lock:
            with open(TOKEN_LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
    except Exception as e:
        pass # Fail silently on logging to keep process alive

# -----------------------------
# DATA VALIDATION
# -----------------------------
def validate_item(item: Dict[str, Any], page_type: str, listing_mode: str) -> Tuple[Dict[str, Any], List[str]]:
    """Validate extracted item and return warnings."""
    warnings = []
    attrs = item.get("attributes", {})
    
    # 1. Evidence Check: Flexible Digit Matching
    price_info = extract_price_info(item.get("price", ""))
    evidence = item.get("price_evidence", "")
    
    if price_info["value"] > 0 and evidence:
        # Extract core price digits for matching
        core_price = str(int(price_info["value"]))  # 299.99 -> "299"
        evidence_digits = re.sub(r'[^\d]', '', evidence)
        
        if core_price not in evidence_digits:
             warnings.append("Price digits not found in evidence quote")

    # 2. Consistency: Status vs Semantics
    p_type = attrs.get("price_type", "").lower()
    status = attrs.get("listing_status", "").lower()
    
    if status == "sold" and "sold" not in p_type and "winning" not in p_type:
        warnings.append(f"Inconsistent: status='sold' but price_type='{p_type}'")
    
    if status == "active" and "sold" in p_type:
        warnings.append(f"Inconsistent: status='active' but price_type='{p_type}'")

    # 3. Required Fields (Context Aware)
    if "TYPE_A" in page_type and listing_mode == "marketplace":
        if not attrs.get("location"):
            warnings.append("Missing location")

    return item, warnings

# --- Attribute Normalization ---
ALIAS_MAP = {
    "shipping": ["delivery", "postage", "ship_cost", "freight", "shipping_cost"],
    "seller": ["vendor", "store", "sold_by", "merchant"],
    "location": ["city", "area", "region", "state", "zip"],
    "condition": ["grade", "quality", "state"],
    "date_raw": ["posted", "sold_date", "date_sold", "time", "sale_date", "ended", "end_date", "listed"],
    "price_type": ["semantics", "price_semantics", "buying_mode", "price_context"] 
}

def normalize_attributes(item: Dict[str, Any]) -> Dict[str, Any]:
    raw_attrs = item.get("attributes", {})
    clean_attrs = {}
    
    # 1. Map Keys
    for k, v in raw_attrs.items():
        k_lower = k.lower().strip()
        mapped_key = k_lower
        for standard, aliases in ALIAS_MAP.items():
            if k_lower == standard or any(a in k_lower for a in aliases):
                mapped_key = standard
                break
        clean_attrs[mapped_key] = v

    # 2. Landed Cost Calculation
    price_val = extract_price_info(item.get("price", "")).get("value", 0.0)
    if shipping := clean_attrs.get("shipping"):
        total = calculate_landed_cost(price_val, str(shipping))
        if total > price_val:
            clean_attrs["landed_cost"] = total

    item["attributes"] = clean_attrs
    return item

# -----------------------------
# IMPROVED DEDUPLICATION
# -----------------------------
def create_item_signature(item: Dict[str, Any], mode: str = "strict") -> str:
    """
    Create item signature for deduplication.
    
    mode='strict': Only exact duplicates (same name, price, seller, location)
    mode='loose': Similar items (used for single listing dedup)
    """
    attrs = item.get("attributes", {})
    
    # Always prefer explicit IDs
    for key in ["listing_id", "url", "sku", "item_number"]:
        if val := attrs.get(key):
            return sha1_text(f"id:{key}:{val}")
    
    if mode == "strict":
        # Exact match - no normalization
        name = (item.get("name") or "").strip().lower()
        price = (item.get("price") or "").strip()
        seller = (attrs.get("seller") or "").strip().lower()
        location = (attrs.get("location") or "").strip().lower()
        condition = (attrs.get("condition") or "").strip().lower()
        
        # All fields must match for dedup
        composite = f"{name}|{price}|{seller}|{location}|{condition}"
        
    else:  # mode == "loose"
        # Just use normalized name (for single listing related items)
        composite = normalize_name(item.get("name", ""))
    
    return sha1_text(composite)

# -----------------------------
# PDF ENGINE
# -----------------------------
def pdf_page_texts(pdf_path: Path) -> List[Tuple[str, str, str]]:
    if not HAS_PYMUPDF:
        raise RuntimeError("PyMuPDF not installed.")
    
    doc = fitz.open(str(pdf_path))
    raw_pages = []
    for i in range(doc.page_count):
        text = collapse_ws(doc.load_page(i).get_text("text") or "")
        raw_pages.append(text)
    doc.close()
    
    windowed_pages = []
    for i, text in enumerate(raw_pages):
        prev_tail = raw_pages[i-1][-CONTEXT_WINDOW_CHARS:] if i > 0 else ""
        next_head = raw_pages[i+1][:CONTEXT_WINDOW_CHARS] if i < len(raw_pages) - 1 else ""
        windowed_pages.append((text, prev_tail, next_head))
        
    return windowed_pages

# -----------------------------
# LLM ENGINE
# -----------------------------
def llm_json(system: str, user_obj: Dict[str, Any], model: str, task_name: str = "Unknown", logger: logging.Logger = None) -> Dict[str, Any]:
    payload = json.dumps(user_obj, ensure_ascii=False)
    client_instance = get_client()
    
    for attempt in range(MAX_RETRIES):
        try:
            resp = client_instance.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": payload},
                ],
                timeout=90.0
            )
            
            if resp.usage:
                log_token_usage(model, resp.usage, task_name)
            
            return json.loads(resp.choices[0].message.content)

        except RateLimitError:
            wait = min(60, (2 ** attempt) + random.random())
            if logger: logger.warning(f"⏱️ Rate limit on {task_name}. Waiting {wait:.1f}s")
            time.sleep(wait)

        except (APITimeoutError, APIConnectionError):
            if attempt == MAX_RETRIES - 1: raise
            wait = 2 ** attempt
            if logger: logger.warning(f"🔌 Connection issue on {task_name}. Retry in {wait}s")
            time.sleep(wait)

        except json.JSONDecodeError:
            if attempt < MAX_RETRIES - 1:
                system += "\n\nCRITICAL: Return ONLY valid JSON. No preamble."
            else:
                raise

        except Exception as e:
            if attempt == MAX_RETRIES - 1: raise
            if logger: logger.error(f"⚠️ Retry {attempt+1}/{MAX_RETRIES} for {task_name}: {e}")
            time.sleep((1 * (2 ** attempt)) + random.random())

# -----------------------------
# SYSTEM CONTEXT PRIMER
# -----------------------------
SYSTEM_PRIMER = """
You are a Research Specialist. Your goal is to extract high-signal technical and market data from messy PDFs.
The user researches: Audio Gear, Photography, Single Board Computers, and Tools.

You categorize content into 5 Types:
TYPE A: Listings Feed (Many rows). SUB-MODES:
    - MARKETPLACE: User-to-user (Craigslist, eBay).
    - RETAIL: Store catalog (Micro Center, B&H).
TYPE B: Single Listing (One item for sale, e.g., eBay item page).
TYPE C: Product Detail (Retail/OEM page, specs, "Add to Cart").
TYPE D: Documentation (Manuals, Spec Sheets).
TYPE E: Editorial (Reviews, Forum Threads).

KEY DISTINCTION - PRICE SEMANTICS:
- ASKING PRICE: What a seller WANTS (Active Listing).
- SOLD PRICE: What a buyer PAID (Historical/Valuation Data).
- MSRP/RETAIL: The official new price.
- CURRENT BID: Ongoing auction price (not final).

OBJECTIVE:
- Identify Source Authority (Manufacturer vs Retailer vs Marketplace).
- Extract Price, Condition, Location, Shipping, Listing Status.
- Distinguish between ACTIVE (Opportunity) and SOLD (Valuation).
"""

# -----------------------------
# PHASE 1: TRIAGE
# -----------------------------
def classify_document(pages: List[Tuple[str, str, str]], file_name: str, logger: logging.Logger) -> Dict[str, Any]:
    p1_text = pages[0][0][:6000]
    mid_idx = len(pages) // 2
    mid_text = pages[mid_idx][0][:4000] if mid_idx > 0 else ""

    system = f"{SYSTEM_PRIMER}\n\nTASK: Analyze document structure, Authority, and Intent. Return valid JSON."
    
    user = {
        "task": "Classify Page Type (A-E), Source Authority, and Market Context",
        "input": {
            "file_name": file_name, 
            "page_1_sample": p1_text, 
            "middle_page_sample": mid_text
        },
        "definitions": {
            "TYPE_A": "Multi-item feed.",
            "TYPE_B": "Single Listing (Used/Marketplace).",
            "TYPE_C": "Product Detail (Retail/New/OEM).",
            "TYPE_D": "Manual/Spec Sheet.",
            "TYPE_E": "Editorial/Forum."
        },
        "output_schema": {
            "page_type": "TYPE_A | TYPE_B | TYPE_C | TYPE_D | TYPE_E",
            "listing_mode": "marketplace | retail_catalog | null",
            "source_authority": "manufacturer_official | retailer_third_party | marketplace_user",
            "market_context": "active_opportunities | historical_completed_sales | mixed",
            "primary_entity": "Main product name",
            "document_year": "integer (year found in copyright/footer) or null",
            "description": "snake_case_filename",
            "strategy": {
                "section_anchors": ["Specific Headings for Type D/E"],
                "poison_sections": ["Headers to HARD STOP extraction", "e.g. 'Related Items', 'Customers also viewed'"],
                "row_markers": ["Cues for Type A rows"],
                "noise_text_examples": ["Sponsored", "Ads", "Related Items"]
            }
        }
    }
    
    raw = llm_json(system, user, model=MODEL_SMART, task_name="Triage_Strategy", logger=logger)
    
    if "strategy" not in raw: raw["strategy"] = {}
    strat = raw["strategy"]
    
    if not strat.get("noise_text_examples"):
        strat["noise_text_examples"] = ["Sponsored", "Add to Watchlist", "Feedback", "Sign in", "Promoted", "Related", "Ad"]
        
    return raw

# -----------------------------
# PHASE 2: EXTRACTION
# -----------------------------
def get_extraction_schema(page_type: str, strategy: Dict[str, Any], context_meta: Dict[str, Any]) -> Dict[str, Any]:
    listing_mode = context_meta.get("listing_mode")
    primary_entity = context_meta.get("primary_entity")
    market_context = context_meta.get("market_context")
    
    base_item = {
        "name": "string",
        "price": "string",
        "confidence": "high | medium | low",
        "price_evidence": "quote"
    }

    # --- TYPE A: LISTINGS ---
    if "TYPE_A" in page_type:
        row_markers = strategy.get("row_markers", ["$", "Item ID"])
        
        # Sub-Mode: Retail Catalog
        if listing_mode == "retail_catalog":
            return {
                "intent": f"Extract CATALOG items. Iterate rows. Max {MAX_ITEMS_PER_PAGE}.",
                "instructions": [
                    f"Use markers: {json.dumps(row_markers)}",
                    "Extract: Price, Condition, Availability, SKU.",
                    "CRITICAL: Extract SKU/Model Number for EVERY item.",
                    "PRICING SEMANTICS: Mark price_type as 'retail_price'.",
                    "IGNORE 'Dates' (irrelevant in catalogs).",
                    "Do not extract 'Related Items'."
                ],
                "output_schema": {
                    "items": [dict(base_item, attributes={
                        "price_type": "retail_price | sale_price",
                        "condition": "new | open_box | used",
                        "availability": "in_stock | backorder | out_of_stock",
                        "sku": "string (REQUIRED)",
                        "notes": "string",
                        "url": "optional_string"
                    })]
                }
            }
        # Sub-Mode: Marketplace (Default)
        else:
            date_req = "Date is REQUIRED if 'market_context' is historical." if market_context == "historical_completed_sales" else "Preserve raw date text."
            return {
                "intent": f"Extract MARKETPLACE items. Iterate rows. Max {MAX_ITEMS_PER_PAGE}.",
                "instructions": [
                    f"Use markers: {json.dumps(row_markers)}",
                    "Extract: Location, Shipping, Condition.",
                    "CRITICAL: Detect 'price_type'. Is this an 'asking_price' (Active) or 'sold_price' (Completed)?",
                    "EVIDENCE RULE: If price_type == 'sold_price', price_evidence MUST include a sold cue (e.g. 'Sold', 'Winning bid', 'Ended').",
                    "CRITICAL: Extract listing_id or url if visible.",
                    date_req,
                    "Ignore 'Sponsored' items."
                ],
                "output_schema": {
                    "items": [dict(base_item, attributes={
                        "price_type": "asking_price | sold_price | current_bid",
                        "condition": "string",
                        "date_raw": "string",
                        "location": "string",
                        "shipping": "string",
                        "seller": "string",
                        "listing_status": "sold | active | ended",
                        "listing_id": "optional_string (EXTRACT IF VISIBLE)",
                        "url": "optional_string"
                    })]
                }
            }

    # --- TYPE B: SINGLE LISTING ---
    elif "TYPE_B" in page_type:
        poison = strategy.get("poison_sections", ["Related Items", "People also viewed"])
        return {
            "intent": "Extract PRIMARY item. IGNORE related items.",
            "instructions": [
                f"PROXIMITY RULE: Extracted data must be textually close to the Primary Entity '{primary_entity}'.",
                f"HARD STOP: Content will be truncated at headers: {json.dumps(poison)}",
                "Focus on the MAIN item for sale.",
                "PRICING: Identify if price is 'asking_price', 'winning_bid', 'buy_it_now', or 'sold_price'.",
                "CONSISTENCY RULE: If listing_status='sold', price_type MUST be 'sold_price' or 'winning_bid'.",
                "CONSISTENCY RULE: If listing_status='active', price_type MUST be 'asking_price' or 'buy_it_now' or 'current_bid'.",
                "Capture 'shipping' to calculate landed cost."
            ],
            "output_schema": {
                "items": [dict(base_item, attributes={
                    "price_type": "asking_price | sold_price | winning_bid | buy_it_now",
                    "condition": "string",
                    "condition_notes": "string",
                    "shipping": "string",
                    "seller": "string",
                    "location": "string",
                    "date_raw": "string",
                    "listing_status": "sold | active | ended",
                    "listing_id": "optional_string"
                })]
            }
        }

    # --- TYPE C: PRODUCT DETAIL ---
    elif "TYPE_C" in page_type:
        poison = strategy.get("poison_sections", ["Related Products", "Accessories"])
        return {
            "intent": "Extract Product Identity & Availability. IGNORE related items.",
            "instructions": [
                f"PROXIMITY RULE: Data must be near Primary Entity '{primary_entity}'.",
                f"HARD STOP: Content will be truncated at headers: {json.dumps(poison)}",
                "Extract Model Number/SKU.",
                "PRICING: Mark as 'retail_price' or 'msrp'.",
                "Extract Key Specs."
            ],
            "output_schema": {
                "items": [dict(base_item, attributes={
                    "price_type": "retail_price | msrp",
                    "sku": "string",
                    "availability": "in_stock | backorder | out_of_stock",
                    "condition": "new | open_box",
                    "specs": {"key": "value"}
                })]
            }
        }

    # --- TYPE D: DOCUMENTATION ---
    elif "TYPE_D" in page_type:
        anchors = strategy.get("section_anchors", ["Specifications", "Technical Data"])
        return {
            "intent": f"Extract Technical Specifications. ONLY from sections: {json.dumps(anchors)}",
            "instructions": [
                "If page does not contain spec tables, return empty list.",
                "Extract technical specifications as key-value pairs.",
                "Handle partial tables: extract what is visible.",
                "Ignore safety warnings, TOC, and Warranty text."
            ],
            "output_schema": {
                "items": [{
                    "name": "Section Name",
                    "attributes": {
                        "tech_specs": {"key": "value"},
                        "io_ports": ["list"]
                    }
                }]
            }
        }

    # --- TYPE E: EDITORIAL ---
    else:
        return {
            "intent": "Extract Sentiment and Consensus.",
            "instructions": ["Extract pros, cons, and warnings."],
            "output_schema": {
                "items": [{
                    "name": "Product",
                    "attributes": {
                        "pros": ["list"],
                        "cons": ["list"],
                        "consensus_verdict": "string",
                        "warnings": ["list"]
                    }
                }]
            }
        }

def extract_page_items(
    text_tuple: Tuple[str, str, str], 
    context: Dict[str, Any],
    logger: logging.Logger
) -> Dict[str, Any]:
    
    main_text, prev_tail, next_head = text_tuple
    page_type = context.get("page_type", "TYPE_A")
    strategy = context.get("strategy", {})
    
    # --- HARD TRUNCATION (POISON SECTION LOGIC) ---
    # Robust method: Case-insensitive search instead of strict Regex split
    dynamic_poison = strategy.get("poison_sections", [])
    default_poison = ["related items", "people who viewed", "customers also viewed", "sponsored"]
    all_poison = list(set(dynamic_poison + default_poison))

    if "TYPE_B" in page_type or "TYPE_C" in page_type:
        lower_text = main_text.lower()
        earliest_idx = len(main_text)
        found = False
        
        for header in all_poison:
            if not header or len(header) < 4: continue
            idx = lower_text.find(header.lower())
            if idx != -1 and idx < earliest_idx:
                earliest_idx = idx
                found = True
        
        if found:
            main_text = main_text[:earliest_idx] + "\n[TRUNCATED AT POISON HEADER]"
            next_head = "" # Kill lookahead context

    schema_config = get_extraction_schema(page_type, strategy, context)
    
    system = f"{SYSTEM_PRIMER}\n\nTASK: {schema_config['intent']}\nReturn valid JSON."

    full_instructions = schema_config['instructions'] + [
        f"NOISE: Ignore lines containing: {json.dumps(strategy.get('noise_text_examples', []))}",
        "EVIDENCE: If extracting a price, you MUST quote the text proving it.",
        "CONFIDENCE: Set 'confidence' (high/medium/low) based on data clarity."
    ]

    user = {
        "page_type": page_type,
        "listing_mode": context.get("listing_mode"),
        "market_context": context.get("market_context"),
        "input_text": f"[PREV]{prev_tail}[/PREV]\n[TARGET]{main_text[:MAX_PAGE_TEXT_CHARS]}[/TARGET]\n[NEXT]{next_head}[/NEXT]",
        "instructions": full_instructions,
        "output_schema": schema_config['output_schema']
    }
    
    return llm_json(system, user, model=MODEL_FAST, task_name=f"Extract_Pg{context.get('page_number')}", logger=logger)

# -----------------------------
# PHASE 3: FILTERING
# -----------------------------
def filter_and_tag_items(items: List[Dict[str, Any]], context: Dict[str, Any], logger: logging.Logger) -> List[Dict[str, Any]]:
    page_type = context.get("page_type", "TYPE_A")
    listing_mode = context.get("listing_mode", "marketplace")
    document_year = context.get("document_year")
    
    # 1. Normalization & Validation
    validated_items = []
    for it in items:
        it = normalize_attributes(it) # Calculates Landed Cost
        
        # Date Parsing
        if raw := it.get("attributes", {}).get("date_raw"):
            iso, inferred = parse_iso_date(raw, anchor_year=document_year)
            if iso:
                it["attributes"]["date_iso"] = iso
                it["attributes"]["date_inferred"] = inferred
        
        # Validation checks
        it, warnings = validate_item(it, page_type, listing_mode)
        if warnings:
            it["attributes"]["data_warnings"] = warnings
            
        validated_items.append(it)
    
    if "TYPE_D" in page_type or "TYPE_E" in page_type or len(validated_items) < 3:
        return validated_items

    # 2. LLM Audit
    simplified_items = []
    for i, it in enumerate(validated_items):
        attrs = it.get("attributes", {})
        hints = []
        for key in ["price_type", "listing_status", "condition", "date_iso"]:
            if val := attrs.get(key):
                hints.append(f"{key}={val}")
        
        simplified_items.append({
            "id": i, 
            "name": it.get("name", "Unknown"), 
            "price": it.get("price", ""),
            "context": "; ".join(hints)
        })

    if listing_mode == "retail_catalog":
        junk_def = "Financing offers, Protection plans, 'Add to Cart' buttons, Service fees"
    else:
        junk_def = "Sponsored ads, Related searches, 'More results', Login prompts"

    system = f"{SYSTEM_PRIMER}\n\nTASK: Quality audit for {listing_mode.upper()} items.\nReturn valid JSON."
    user = {
        "task": f"Mark noise/junk. JUNK DEFINITION: {junk_def}",
        "items": simplified_items,
        "output_schema": {
            "ids_to_drop": [],
            "ids_parts_only": [],
            "ids_accessory": []
        }
    }
    
    result = llm_json(system, user, model=MODEL_FAST, task_name="Filter_Tag", logger=logger)
    
    final_items = []
    drop_ids = set(result.get("ids_to_drop", []))
    
    for i, item in enumerate(validated_items):
        if i in drop_ids: continue
        if i in result.get("ids_parts_only", []): item["attributes"]["is_parts_only"] = True
        if i in result.get("ids_accessory", []): item["attributes"]["is_accessory"] = True
        final_items.append(item)
        
    return final_items

# -----------------------------
# PHASE 4: SUMMARY
# -----------------------------
def summarize_doc(doc_meta: Dict[str, Any], items: List[Dict[str, Any]], logger: logging.Logger) -> List[str]:
    page_type = doc_meta.get("page_type", "TYPE_A")
    source_auth = doc_meta.get("source_authority", "unknown")
    market_ctx = doc_meta.get("market_context", "unknown")
    
    task_prefix = ""
    if source_auth == "manufacturer_official":
        task_prefix = "SOURCE IS OFFICIAL MANUFACTURER. Treat specs as GROUND TRUTH."
    elif source_auth == "retailer_third_party":
        task_prefix = "Source is Retailer. Specs are secondary to official data."
    
    if market_ctx == "historical_completed_sales":
        task_prefix += " DATA IS COMPLETED SALES. Focus on VALUATION."

    if "TYPE_A" in page_type:
        task = f"{task_prefix} Market Analyst. Identify price spread (Sold vs Active), availability trends, and outliers."
    elif "TYPE_B" in page_type or "TYPE_C" in page_type:
        task = f"{task_prefix} Procurement Specialist. Verify completeness, hidden costs, and value."
    elif "TYPE_D" in page_type:
        task = "Technical Librarian. Summarize key capabilities, limitations, and compatibility."
    else:
        task = "Review Aggregator. Summarize community consensus and critical warnings."

    if not items: return ["No data extracted."]

    # Stratified sampling with size guard
    sorted_items = sorted(items, key=lambda x: extract_price_info(x.get("price", ""))["value"])
    
    if len(sorted_items) > 35:
        sample = sorted_items[:5] + sorted_items[-5:] + sorted_items[10:35]
    else:
        sample = sorted_items

    system = f"{SYSTEM_PRIMER}\n\nTASK: {task}\nReturn valid JSON."
    user = {
        "task": "Generate executive summary.",
        "data_sample": sample,
        "output_schema": {"bullets": ["Insight 1", "Insight 2"]}
    }
    
    try:
        res = llm_json(system, user, model=MODEL_SMART, task_name="Summarize", logger=logger)
        return res.get("bullets", []) or ["Summary failed."]
    except Exception as e:
        return [f"Error generating summary: {e}"]

# -----------------------------
# RENDERER
# -----------------------------
def render_markdown(doc_meta: Dict[str, Any], items: List[Dict[str, Any]], summary: List[str]) -> str:
    timestamp = now_stamp()
    page_type = doc_meta.get("page_type", "TYPE_A")
    listing_mode = doc_meta.get("listing_mode", "standard")
    source_auth = doc_meta.get("source_authority", "unknown")
    market_ctx = doc_meta.get("market_context", "unknown")
    
    lines = [
        f"# {doc_meta.get('description', 'Research Report')}",
        f"**Source:** `{doc_meta.get('source_name')}`",
        f"**Authority:** {source_auth.upper()} | **Context:** {market_ctx.upper()}",
        f"**Type:** {page_type} ({listing_mode}) | **Date:** {timestamp}",
        "",
        "## Executive Summary"
    ]
    lines.extend([f"- {s}" for s in summary])
    lines.append("")
    
    # 1. TABLE RENDERER (Type A)
    if "TYPE_A" in page_type:
        if listing_mode == "retail_catalog":
            col_header = "Stock"
        else:
            col_header = "Date"
            
        lines.append("## Market Listings")
        lines.append(f"| Name | Price (Type) | {col_header} | Status | Details |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        
        # Sort Logic: ACTIVE first, then SOLD. Then by Price/Date.
        def sort_key(x):
            attrs = x.get("attributes", {})
            
            # Status Grouping: Active/Available = 1, Sold/Ended = 0
            stat = attrs.get("listing_status", "").lower()
            is_active = 1 if stat in ["active", "available", "in_stock"] else 0
            
            # Secondary sorts
            price = extract_price_info(x.get("price", ""))["value"]
            date_val = attrs.get("date_iso", "")
            
            return (is_active, date_val, price)

        items.sort(key=sort_key, reverse=True)
        
        for it in items:
            name = (it.get("name") or "Unknown").replace("|", " ")
            price_raw = (it.get("price") or "N/A").replace("|", " ")
            attrs = dict(it.get("attributes", {}))
            
            # Semantic Price Display
            p_type = attrs.get("price_type", "").replace("_", " ").upper()
            if "SOLD" in p_type or "WINNING" in p_type:
                price_display = f"**{price_raw}**<br>✅ *{p_type}*"
            else:
                price_display = f"{price_raw}<br>*{p_type}*"

            # Dynamic Column Content
            mid_col = "-"
            if listing_mode == "retail_catalog":
                 if avail := attrs.get("availability"): mid_col = avail.upper()
            else:
                if attrs.get("date_iso"):
                    mid_col = f"**{attrs['date_iso']}**"
                    if attrs.get("date_inferred"): mid_col += "*"
                elif attrs.get("date_raw"):
                    mid_col = attrs.get("date_raw")
            
            # Status
            status = (attrs.get("listing_status") or attrs.get("availability") or "unknown").upper()
            
            # Details
            details = []
            if lc := attrs.pop("landed_cost", None): details.append(f"🚢 **Total: ${lc:,.2f}**")
            if attrs.pop("is_parts_only", False): details.append("🔴 **PARTS**")
            
            # Confidence Warning
            if it.get("confidence") == "low": details.append("⚠️ Low Conf.")
            if warns := attrs.pop("data_warnings", []): details.append(f"⚠️ {len(warns)} Warns")
            
            if loc := attrs.pop("location", None): details.append(f"📍 {loc}")
            if sku := attrs.pop("sku", None): details.append(f"🆔 {sku}")
            
            lines.append(f"| {name} | {price_display} | {mid_col} | {status} | {'<br>'.join(details)} |")
        
        if listing_mode != "retail_catalog":
            lines.append("\n*(*) Date year inferred.*")

    # 2. FACT CARD RENDERER (Type B & C)
    elif "TYPE_B" in page_type or "TYPE_C" in page_type:
        lines.append("## Primary Entity")
        for it in items[:1]: 
            name = it.get("name")
            price = it.get("price") or "N/A"
            attrs = it.get("attributes", {})
            p_type = attrs.get("price_type", "").upper()
            
            lines.append(f"### {name}")
            lines.append(f"**Price:** {price} ({p_type})")
            if lc := attrs.get("landed_cost"):
                 lines.append(f"**Landed Cost:** ${lc:,.2f}")
            
            # Confidence warning for single listings
            if it.get("confidence") == "low":
                lines.append("> ⚠️ **Confidence:** LOW - Verify manually")
            
            lines.append("---")
            
            if sku := attrs.get("sku"): lines.append(f"- **SKU:** `{sku}`")
            if avail := attrs.get("availability"): lines.append(f"- **Availability:** {avail.upper()}")
            if l_stat := attrs.get("listing_status"): lines.append(f"- **Status:** {l_stat.upper()}")
            if ship := attrs.get("shipping"): lines.append(f"- **Shipping:** {ship}")
            if loc := attrs.get("location"): lines.append(f"- **Location:** {loc}")
            if cond := attrs.get("condition"): lines.append(f"- **Condition:** {cond}")
            if notes := attrs.get("condition_notes"): lines.append(f"> **Notes:** {notes}")
            if warns := attrs.get("data_warnings"): lines.append(f"> **⚠️ Validation:** {', '.join(warns)}")
            
            if specs := attrs.get("specs"):
                lines.append("\n**Specifications:**")
                for k,v in specs.items():
                    lines.append(f"- **{k}:** {v}")

    # 3. DOC RENDERER (Type D & E)
    else:
        lines.append("## Technical & Editorial Data")
        for it in items:
            name = it.get("name", "Section")
            attrs = it.get("attributes", {})
            lines.append(f"### {name}")
            
            if tech := attrs.get("tech_specs"):
                lines.append("**Specs:**")
                for k,v in tech.items(): lines.append(f"- {k}: {v}")
            if io := attrs.get("io_ports"):
                lines.append(f"**I/O:** {', '.join(io)}")
            if pros := attrs.get("pros"):
                lines.append("**✅ Pros:**")
                lines.extend([f"- {p}" for p in pros])
            if cons := attrs.get("cons"):
                lines.append("**❌ Cons:**")
                lines.extend([f"- {c}" for c in cons])
            lines.append("")

    return "\n".join(lines)

# -----------------------------
# MAIN PROCESSOR
# -----------------------------
class ResearchAssistant:
    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        self.base_archive = self.source_path.parent.parent / DEFAULT_ARCHIVE_FOLDER
        self.errors_dir = self.base_archive.parent / DEFAULT_ERRORS_FOLDER
        self.logger = setup_logging(self.source_path)

    def process(self):
        self.logger.info(f"🚀 Processing: {self.source_path.name}")
        if HAS_TQDM: 
            print(f"🚀 Processing: {self.source_path.name}")
        
        try:
            if not self.source_path.suffix.lower() == ".pdf":
                self.logger.error("Not a PDF.")
                return

            pages_data = pdf_page_texts(self.source_path)
            if not pages_data: raise ValueError("Empty PDF.")
            
            # 1. Triage
            self.logger.info("🧠 Analyzing Document Type...")
            triage = classify_document(pages_data, self.source_path.name, self.logger)
            triage["source_name"] = self.source_path.name
            
            self.logger.info(f"→ Identified: {triage.get('page_type')} ({triage.get('listing_mode')})")
            
            # 2. Extraction Strategy
            self.logger.info(f"⚡ Extracting {len(pages_data)} pages...")
            all_items = []
            pages_to_scan = pages_data
            page_type = triage.get("page_type", "")
            
            if "TYPE_B" in page_type:
                 pages_to_scan = pages_data[:4]
                 self.logger.debug("Optimization: Scanning first 4 pages for Single Listing.")
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
                futures = {
                    exe.submit(extract_page_items, pg, {
                        "page_number": i+1,
                        "page_type": page_type,
                        "listing_mode": triage.get("listing_mode"),
                        "primary_entity": triage.get("primary_entity"),
                        "market_context": triage.get("market_context"),
                        "source_authority": triage.get("source_authority"),
                        "document_year": triage.get("document_year"),
                        "strategy": triage.get("strategy", {})
                    }, self.logger): i 
                    for i, pg in enumerate(pages_to_scan) if len(pg[0]) > 50
                }
                
                iterable = as_completed(futures)
                if HAS_TQDM:
                    iterable = tqdm(iterable, total=len(futures), desc="Extracting", unit="pg")

                for fut in iterable:
                    try:
                        res = fut.result()
                        new_items = res.get("items", [])
                        all_items.extend(new_items)
                    except Exception as e:
                        self.logger.error(f"Page failed: {e}")

            # ==========================================
            # 3. MODE-AWARE DEDUPLICATION
            # ==========================================
            listing_mode = triage.get("listing_mode")
            
            if listing_mode == "retail_catalog":
                # Retail: No dedup needed (each product should be unique)
                self.logger.info("🔍 Skipping dedup (retail catalog mode)")
                unique = all_items
                
            elif "TYPE_B" in page_type or "TYPE_C" in page_type:
                # Single listing: Light dedup (remove related items that leaked)
                unique = []
                seen_names = set()
                
                for it in all_items:
                    name_norm = normalize_name(it.get("name", ""))
                    if name_norm and name_norm not in seen_names:
                        seen_names.add(name_norm)
                        unique.append(it)
                    elif not name_norm:
                        unique.append(it)  # Keep items without names
                
                removed = len(all_items) - len(unique)
                self.logger.info(f"🔍 Dedupe (single listing): {len(all_items)} -> {len(unique)} (removed {removed} related items)")
                
            else:
                # Marketplace feed: STRICT dedup (only exact duplicates)
                unique = []
                seen_signatures = {}
                
                for it in all_items:
                    sig = create_item_signature(it, mode="strict")
                    
                    if sig not in seen_signatures:
                        seen_signatures[sig] = it.get("name", "Unknown")
                        unique.append(it)
                    else:
                        # Log what was deduplicated
                        self.logger.debug(f"Dedup: '{it.get('name')}' matches '{seen_signatures[sig]}'")
                
                removed = len(all_items) - len(unique)
                self.logger.info(f"🔍 Dedupe (marketplace): {len(all_items)} -> {len(unique)} (removed {removed} exact duplicates)")

            # 4. Filter & Validation
            self.logger.info("🧹 Filtering & Normalizing...")
            clean_items = filter_and_tag_items(unique, triage, self.logger)

            # 5. Summary
            self.logger.info("📝 Summarizing...")
            summary = summarize_doc(triage, clean_items, self.logger)

            # 6. Quality Metrics
            quality_metrics = {
                "total_items": len(clean_items),
                "items_with_dates": sum(1 for it in clean_items if it.get("attributes", {}).get("date_iso")),
                "low_confidence_items": sum(1 for it in clean_items if it.get("confidence") == "low"),
                "items_with_warnings": sum(1 for it in clean_items if it.get("attributes", {}).get("data_warnings")),
                "dedup_stats": {
                    "raw_extracted": len(all_items),
                    "after_dedup": len(unique),
                    "after_filter": len(clean_items),
                    "dedup_mode": "none" if listing_mode == "retail_catalog" else ("loose" if "TYPE_B" in page_type or "TYPE_C" in page_type else "strict")
                }
            }

            # 7. Save
            ensure_dir(self.base_archive)
            base_name = f"{now_stamp()}_{safe_filename(triage.get('description'))}"
            
            write_json(self.base_archive / f"{base_name}_data.json", 
                      {"meta": triage, "quality": quality_metrics, "summary": summary, "items": clean_items})
            
            write_text(self.base_archive / f"{base_name}_report.md", 
                      render_markdown(triage, clean_items, summary))
            
            shutil.copy(self.source_path, self.base_archive / f"{base_name}_source.pdf")
            
            if (self.base_archive / f"{base_name}_data.json").exists():
                os.remove(self.source_path)
                self.logger.info("✅ Done.")
                if HAS_TQDM:
                    print("✅ Done.")

        except Exception as e:
            self.logger.critical(f"💥 Fatal Error: {e}")
            self.logger.debug(traceback.format_exc())
            ensure_dir(self.errors_dir)
            shutil.move(self.source_path, self.errors_dir / self.source_path.name)
            write_text(self.errors_dir / f"{self.source_path.name}_error.txt", traceback.format_exc())

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        ResearchAssistant(sys.argv[1]).process()