import json
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from config import CACHE_FILE, CACHE_MIN_SUCCESS_RATE, CACHE_STALENESS_DAYS
from utils_logging import log_event

class FingerprintCache:
    """Manages extraction plan caching to reduce API costs on repeat page structures."""
    
    def __init__(self):
        self.cache_file = Path(CACHE_FILE)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        """Load existing cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    log_event(f"Loaded fingerprint cache with {len(cache)} entries")
                    return cache
            except Exception as e:
                log_event(f"Error loading cache: {e}", "warning")
                return {}
        else:
            log_event("No existing cache found - will create new one")
            return {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            # Ensure parent directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            log_event(f"Cache saved: {len(self.cache)} entries")
        except Exception as e:
            log_event(f"Error saving cache: {e}", "error")
    
    def generate_fingerprint(self, brief: dict, raw_html: str) -> str:
        """
        Generate a unique fingerprint for this page structure.
        
        Uses:
        - Domain (from JSON-LD or URL patterns)
        - Page type (from JSON-LD @type)
        - Key structural markers (class patterns, container types)
        """
        from bs4 import BeautifulSoup
        
        signals = []
        
        # 1. Extract domain from JSON-LD or HTML
        json_ld = brief.get("json_ld_data", [])
        if json_ld:
            first_blob = json_ld[0] if isinstance(json_ld, list) else json_ld
            url = first_blob.get("url", "") or first_blob.get("@id", "")
            if url:
                # Extract domain from URL
                domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                if domain_match:
                    signals.append(f"domain:{domain_match.group(1)}")
            
            # 2. Page type from JSON-LD
            page_type = first_blob.get("@type", "")
            if page_type:
                signals.append(f"type:{page_type}")
        
        # 3. Structural markers from HTML
        soup = BeautifulSoup(brief.get("full_clean_html", ""), "lxml")
        
        # Find dominant container patterns
        # Common e-commerce patterns
        patterns = [
            's-item', 's-card', 'product', 'listing', 'result',
            'cl-search-result', 'product-card', 'product_wrapper'
        ]
        
        for pattern in patterns:
            elements = soup.find_all(class_=re.compile(pattern, re.I))
            if len(elements) >= 3:  # Found a repeating pattern
                signals.append(f"container:{pattern}")
                break
        
        # Key data indicators
        has_price = bool(soup.find(class_=re.compile(r'price', re.I)))
        has_title = bool(soup.find(class_=re.compile(r'title', re.I)))
        signals.append(f"price:{has_price}")
        signals.append(f"title:{has_title}")
        
        # 4. Create hash
        fingerprint_string = "|".join(signals)
        fingerprint = hashlib.md5(fingerprint_string.encode()).hexdigest()[:16]
        
        log_event(f"Generated fingerprint: {fingerprint} ({fingerprint_string})")
        return fingerprint
    
    def get_cached_plan(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached plan if it exists and is still valid.
        
        Returns None if:
        - No cache entry exists
        - Success rate is too low
        - Plan is stale (not used recently)
        """
        if fingerprint not in self.cache:
            log_event("⚠ Cache MISS - new page structure")
            return None
        
        entry = self.cache[fingerprint]
        
        # Check success rate
        success_rate = entry.get("success_rate", 0)
        if success_rate < CACHE_MIN_SUCCESS_RATE:
            log_event(f"⚠ Cache entry exists but success rate too low: {success_rate:.2%}")
            return None
        
        # Check staleness
        last_used = datetime.fromisoformat(entry.get("last_used", "2000-01-01"))
        days_since_use = (datetime.now() - last_used).days
        if days_since_use > CACHE_STALENESS_DAYS:
            log_event(f"⚠ Cache entry exists but stale (last used {days_since_use} days ago)")
            return None
        
        log_event(f"✓ Cache HIT - Using cached plan (success: {success_rate:.1%}, used: {entry.get('use_count', 0)} times)")
        
        return {
            "context": entry["context"],
            "plan": entry["plan"],
            "fingerprint": fingerprint
        }
    
    def save_plan(self, fingerprint: str, context: dict, plan: dict):
        """Save a new extraction plan to cache."""
        self.cache[fingerprint] = {
            "context": context,
            "plan": plan,
            "success_rate": 1.0,  # Assume perfect until we get data
            "use_count": 1,
            "total_extractions": 1,
            "successful_extractions": 1,
            "created": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat()
        }
        self._save_cache()
        log_event(f"💾 Saved new plan to cache: {fingerprint}")
    
    def update_stats(self, fingerprint: str, completeness_score: int):
        """Update cache statistics after an extraction."""
        if fingerprint not in self.cache:
            return
        
        entry = self.cache[fingerprint]
        entry["use_count"] = entry.get("use_count", 0) + 1
        entry["total_extractions"] = entry.get("total_extractions", 0) + 1
        entry["last_used"] = datetime.now().isoformat()
        
        # Update success rate (consider >80% completeness as success)
        if completeness_score >= 80:
            entry["successful_extractions"] = entry.get("successful_extractions", 0) + 1
        
        entry["success_rate"] = entry["successful_extractions"] / entry["total_extractions"]
        
        self._save_cache()
        log_event(f"📊 Updated cache stats: {fingerprint} (success: {entry['success_rate']:.1%})")
    
    def get_stats(self) -> dict:
        """Get cache statistics for reporting."""
        total_entries = len(self.cache)
        total_uses = sum(entry.get("use_count", 0) for entry in self.cache.values())
        avg_success = sum(entry.get("success_rate", 0) for entry in self.cache.values()) / max(total_entries, 1)
        
        return {
            "total_cached_plans": total_entries,
            "total_cache_hits": total_uses,
            "average_success_rate": avg_success
        }

# Global cache instance
cache = FingerprintCache()