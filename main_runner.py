import time
import os
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import config
import html_brief
import planner
import extractor
import verifier
import reporter
import fingerprint
from utils_logging import log_event

class ResearchPipelineHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory: 
            return
        
        filename = event.src_path
        
        # Ignore system files
        if os.path.basename(filename).startswith("._") or ".DS_Store" in filename: 
            return
        
        # Only process HTML files
        if not filename.endswith(".html"): 
            return

        log_event(f"📥 New file detected: {filename}")
        self.process_file_safely(Path(filename))

    def process_file_safely(self, file_path: Path):
        """Process a single HTML file through the extraction pipeline."""
        
        # --- 1. Network Stabilization ---
        # Wait for file to finish copying/downloading
        historical_size = -1
        while True:
            try:
                current_size = file_path.stat().st_size
                if current_size == historical_size and current_size > 0: 
                    break
                historical_size = current_size
                time.sleep(config.NETWORK_STABILIZATION_TIME)
            except FileNotFoundError:
                return

        # --- 2. Execution Pipeline ---
        try:
            log_event("=" * 80)
            log_event(f"🚀 Processing: {file_path.name}")
            log_event("=" * 80)
            
            # Read raw HTML
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_html = f.read()

            # STEP A: Create HTML Brief (Python - Free)
            log_event("\n📋 STEP A: Creating HTML Brief...")
            brief = html_brief.create_brief(raw_html)
            
            # STEP B: Generate Fingerprint & Check Cache
            log_event("\n🔍 STEP B: Checking Fingerprint Cache...")
            fp = fingerprint.cache.generate_fingerprint(brief, raw_html)
            cached = fingerprint.cache.get_cached_plan(fp)
            
            if cached:
                # CACHE HIT - Use existing plan
                log_event("✅ Using cached extraction plan")
                context_guidelines = cached["context"]
                plan = cached["plan"]
                cost_saved = "$0.10"  # Saved Context + Planning costs
                cache_hit = True
            else:
                # CACHE MISS - Full analysis required
                log_event("⚠️  Cache miss - performing full analysis")
                
                # STEP C: Context Analysis (GPT-4o - ~$0.03-0.05)
                log_event("\n🧠 STEP C: Context Analysis...")
                context_guidelines = planner.analyze_context(brief)
                
                # STEP D: Technical Planning (GPT-4o-mini - ~$0.003)
                log_event("\n🔧 STEP D: Technical Planning...")
                plan = planner.create_technical_plan(brief, context_guidelines)
                
                # Save to cache for future use
                fingerprint.cache.save_plan(fp, context_guidelines, plan)
                cache_hit = False
            
            # STEP E: Extraction (Python - Free)
            log_event("\n⚙️  STEP E: Executing Extraction...")
            raw_data = extractor.execute_extraction(raw_html, brief, plan)
            log_event(f"   Extracted {len(raw_data)} fields")
            
            # STEP F: Verification & Summary (GPT-4o - ~$0.03-0.05)
            log_event("\n✅ STEP F: Verification & Summary...")
            final_review = verifier.verify_and_summarize(raw_data, context_guidelines)
            
            # Update cache statistics
            completeness = final_review.get("completeness_score", 0)
            if isinstance(completeness, str):
                # Handle "90/100" format
                completeness = int(completeness.split('/')[0]) if '/' in completeness else int(completeness)
            
            fingerprint.cache.update_stats(fp, completeness)
            
            # STEP G: Generate Report
            log_event("\n📊 STEP G: Generating Report...")
            report_info = {
                "cache_hit": cache_hit,
                "fingerprint": fp,
                "completeness": completeness
            }
            reporter.generate_report(
                file_path.name, 
                raw_data, 
                plan, 
                final_review, 
                context_guidelines,
                report_info
            )
            
            # STEP H: Archive
            archive_path = config.ARCHIVE_DIR / file_path.name
            shutil.move(str(file_path), str(archive_path))
            
            # Final summary
            log_event("\n" + "=" * 80)
            if cache_hit:
                log_event(f"✅ SUCCESS (Cache Hit) - Archived: {file_path.name}")
            else:
                log_event(f"✅ SUCCESS (Full Analysis) - Archived: {file_path.name}")
            log_event("=" * 80 + "\n")

        except Exception as e:
            log_event(f"\n❌ CRITICAL ERROR: {e}", "error")
            import traceback
            log_event(traceback.format_exc(), "error")
            
            # Move to error directory
            try:
                error_path = config.ERROR_DIR / file_path.name
                shutil.move(str(file_path), str(error_path))
                log_event(f"Moved to error directory: {error_path}")
            except:
                pass

def start_watching():
    """Start the file watcher to monitor the queue directory."""
    
    # Ensure directories exist
    config.QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    config.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    config.ERROR_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Display startup info
    log_event("\n" + "=" * 80)
    log_event("🚀 SMART EXTRACTION PIPELINE - STARTED")
    log_event("=" * 80)
    log_event(f"📂 Monitoring: {config.QUEUE_DIR}")
    log_event(f"💾 Cache file: {config.CACHE_FILE}")
    log_event(f"🧠 Smart Model: {config.MODEL_SMART}")
    log_event(f"⚡ Fast Model: {config.MODEL_FAST}")
    
    # Show cache stats
    stats = fingerprint.cache.get_stats()
    log_event(f"\n📊 Cache Statistics:")
    log_event(f"   Cached Plans: {stats['total_cached_plans']}")
    log_event(f"   Total Uses: {stats['total_cache_hits']}")
    log_event(f"   Avg Success: {stats['average_success_rate']:.1%}")
    
    log_event("\n⏳ Waiting for HTML files...")
    log_event("=" * 80 + "\n")
    
    # Start watching
    event_handler = ResearchPipelineHandler()
    observer = Observer()
    observer.schedule(event_handler, str(config.QUEUE_DIR), recursive=False)
    observer.start()
    
    try:
        while True: 
            time.sleep(1)
    except KeyboardInterrupt:
        log_event("\n🛑 Shutting down...")
        observer.stop()
    
    observer.join()

if __name__ == "__main__":
    start_watching()