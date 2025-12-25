from bs4 import BeautifulSoup, Comment
import json
from utils_logging import log_event

def create_brief(html_content: str) -> dict:
    """
    Create a comprehensive brief from HTML.
    
    Args:
        html_content: The actual HTML string content (NOT a file path!)
    
    Strategy: SEND FULL CLEANED HTML
    - Extract JSON-LD (structured data gold mine)
    - Send FULL cleaned HTML (no truncation, no guessing)
    - Gemini 2.5 Flash has 1M token window - plenty of headroom
    
    Cost: ~10-15K tokens per page = $0.001-0.002 in API calls
    Value: 95%+ extraction accuracy on first pass
    """
    
    # Validate input
    if not isinstance(html_content, str):
        raise TypeError(f"Expected string, got {type(html_content).__name__}")
    
    if len(html_content) < 100:
        raise ValueError(f"HTML content is too short ({len(html_content)} chars) - may be a file path instead of content")
    
    log_event(f"   📄 Processing HTML: {len(html_content):,} characters ({len(html_content) / 1024:.1f} KB)")
    
    soup = BeautifulSoup(html_content, "lxml")

    # --- STEP 1: EXTRACT JSON-LD FIRST (Before cleaning) ---
    json_ld_data = []
    scripts = soup.find_all("script", type="application/ld+json")
    
    for s in scripts:
        try:
            content = s.string
            if content:
                data = json.loads(content.strip())
                json_ld_data.append(data)
        except:
            continue
    
    if json_ld_data:
        log_event(f"   ✅ Found {len(json_ld_data)} JSON-LD structured data blocks")
    else:
        log_event(f"   ℹ️  No JSON-LD structured data found")
            
    # --- STEP 2: CLEAN THE NOISE ---
    # Remove bloat but keep ALL content structure
    removed_tags = 0
    
    # Remove script, style, and other non-content tags
    for tag in soup(["script", "style", "svg", "path", "noscript", "iframe", "meta", "link"]):
        tag.decompose()
        removed_tags += 1
    
    # Remove HTML comments
    comment_count = 0
    for element in soup(text=lambda text: isinstance(text, Comment)):
        element.extract()
        comment_count += 1
    
    if removed_tags > 0:
        log_event(f"   🗑️  Removed {removed_tags} non-content tags")
    if comment_count > 0:
        log_event(f"   🗑️  Removed {comment_count} HTML comments")

    # --- STEP 3: BASE64 STRIPPING ---
    # Base64 images/fonts are token killers (100KB+ of gibberish)
    base64_removed = 0
    
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("data:image"):
            img["src"] = "[BASE64_REMOVED]"
            base64_removed += 1
        # Keep all other attributes - they might be useful
    
    if base64_removed > 0:
        log_event(f"   🖼️  Removed {base64_removed} Base64 inline images")

    # --- STEP 4: GENERATE FULL CLEAN HTML ---
    # NO TRUNCATION - send everything
    # Gemini 2.5 Flash can handle it (1M token window)
    clean_html = soup.body.prettify() if soup.body else soup.prettify()
    
    # Validate we actually got content
    if len(clean_html) < 50:
        raise ValueError(f"Cleaned HTML is suspiciously short ({len(clean_html)} chars) - something went wrong")
    
    original_size_kb = len(html_content) / 1024
    cleaned_size_kb = len(clean_html) / 1024
    reduction_pct = ((original_size_kb - cleaned_size_kb) / original_size_kb) * 100 if original_size_kb > 0 else 0
    
    log_event(f"   ✅ Cleaning complete: {original_size_kb:.1f}KB → {cleaned_size_kb:.1f}KB ({reduction_pct:.1f}% reduction)")
    
    # Estimated tokens (rough: 1 token ≈ 4 chars)
    estimated_tokens = len(clean_html) // 4
    log_event(f"   📊 Estimated tokens: ~{estimated_tokens:,}")
    
    brief = {
        "json_ld_data": json_ld_data,        # Structured data (if present)
        "full_clean_html": clean_html,       # Complete cleaned HTML
        "original_size_kb": original_size_kb,
        "cleaned_size_kb": cleaned_size_kb,
        "estimated_tokens": estimated_tokens,
        "base64_images_removed": base64_removed
    }
    
    return brief