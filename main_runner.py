"""
main_runner.py - Smart Web Data Extraction Pipeline
Two-step validation for optimal cost/quality

Architecture:
1. Clean HTML (Python)
2. Form Hypothesis (GPT-4o-mini on sample)
3. Extract Data (Gemini on full HTML)
4A. Format Data (GPT-4o-mini converts JSON to markdown)
4B. Validate & Insights (GPT-4o adds strategic oversight)
5. Generate Reports
"""

import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import config
import html_brief
import analyzer
import gemini_extractor
import formatter
import validator
import reporter
from utils_logging import log_event

class HTMLFileHandler(FileSystemEventHandler):
    """Watches for new HTML files in the queue directory."""
    
    def __init__(self):
        self.processing = set()
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Skip macOS metadata files
        if file_path.name.startswith('._'):
            log_event(f"   ⏭️  Skipping macOS metadata file: {file_path.name}")
            return
        
        if file_path.suffix.lower() in ['.html', '.htm']:
            # Check if already processing
            if file_path in self.processing:
                return
            
            # Check if file actually exists (watchdog can trigger on moved files)
            if not file_path.exists():
                return
            
            log_event(f"\n📥 New file detected: {file_path.name}")
            
            # Wait for file to finish copying over network
            log_event(f"   ⏳ Waiting for file transfer to complete...")
            last_size = 0
            stable_count = 0
            max_wait = 30
            wait_count = 0
            
            while wait_count < max_wait:
                time.sleep(1)
                wait_count += 1
                
                if not file_path.exists():
                    return
                
                current_size = file_path.stat().st_size
                
                if current_size == last_size:
                    stable_count += 1
                    if stable_count >= 3:
                        log_event(f"   ✅ Transfer complete: {current_size / 1024:.1f} KB")
                        break
                else:
                    stable_count = 0
                    last_size = current_size
                    log_event(f"   📊 Receiving: {current_size / 1024:.1f} KB...")
            
            # Double-check file still exists and has content
            if not file_path.exists():
                return
            
            if file_path.stat().st_size < 1000:
                log_event(f"   ⚠️  File too small after transfer - may be incomplete", "warning")
                return
            
            self.processing.add(file_path)
            try:
                process_file_safely(file_path)
            finally:
                self.processing.discard(file_path)


def process_file_safely(file_path: Path):
    """
    Process a file with comprehensive error handling.
    """
    try:
        # Check if file exists and has content
        if not file_path.exists():
            log_event(f"⚠️  File does not exist: {file_path}", "warning")
            return
        
        file_size = file_path.stat().st_size
        if file_size < 1000:
            log_event(f"⚠️  File is too small ({file_size} bytes) - may be corrupted", "warning")
            log_event(f"   Skipping: {file_path.name}", "warning")
            error_path = config.ERROR_DIR / file_path.name
            file_path.rename(error_path)
            return
        
        log_event("=" * 80)
        log_event(f"🚀 Processing: {file_path.name}")
        log_event(f"   File size: {file_size / 1024:.1f} KB")
        log_event("=" * 80)
        
        # === STEP 1: READ AND CLEAN HTML ===
        log_event("\n📋 Step 1: Reading and Cleaning HTML...")
        
        try:
            html_content = file_path.read_text(encoding='utf-8')
            log_event(f"   ✅ Read {len(html_content):,} characters from file")
        except UnicodeDecodeError:
            log_event(f"   ⚠️  UTF-8 decode failed, trying latin-1...", "warning")
            html_content = file_path.read_text(encoding='latin-1')
            log_event(f"   ✅ Read {len(html_content):,} characters with latin-1 encoding")
        
        brief = html_brief.create_brief(html_content)
        
        # === STEP 2A: FORM HYPOTHESIS ===
        log_event("\n🔍 Step 2A: Forming Hypothesis...")
        html_sample = brief.get('full_clean_html', '')[:50000]
        hypothesis = analyzer.analyze_page(html_sample)
        
        # === STEP 2B: EXTRACT DATA ===
        log_event("\n⚡ Step 2B: Extracting Data...")
        full_html = brief.get('full_clean_html', '')
        extracted_data = gemini_extractor.extract_data(full_html, hypothesis)
        
        # === STEP 3A: FORMAT DATA ===
        log_event("\n📝 Step 3A: Formatting Data...")
        formatted_markdown = formatter.format_data(hypothesis, extracted_data)
        
        # === STEP 3B: VALIDATE & ADD INSIGHTS ===
        log_event("\n✅ Step 3B: Validation & Insights...")
        validation_result = validator.validate_report(
            hypothesis,
            extracted_data,
            formatted_markdown,
            file_path.name
        )
        
        # === STEP 4: GENERATE OUTPUT FILES ===
        log_event("\n📊 Step 4: Generating Output Files...")
        md_path, json_path, debug_path = reporter.generate_reports(
            hypothesis,
            extracted_data,
            formatted_markdown,
            validation_result,
            file_path.name
        )
        
        # === FINAL STATUS ===
        status = validation_result.get('status', 'unknown')
        
        if not file_path.exists():
            log_event(f"\n⚠️  File already moved or deleted: {file_path.name}", "warning")
            return
        
        if status == 'success':
            archive_path = config.ARCHIVE_DIR / file_path.name
            file_path.rename(archive_path)
            log_event("\n" + "=" * 80)
            log_event(f"✅ SUCCESS - Archived: {file_path.name}")
            log_event("=" * 80)
        
        elif status == 'extraction_incomplete':
            archive_path = config.ARCHIVE_DIR / file_path.name
            file_path.rename(archive_path)
            log_event("\n" + "=" * 80)
            log_event(f"⚠️  INCOMPLETE - Check report: {file_path.name}")
            log_event("=" * 80)
        
        else:
            error_path = config.ERROR_DIR / file_path.name
            file_path.rename(error_path)
            log_event("\n" + "=" * 80)
            log_event(f"❌ FAILED - Moved to errors: {file_path.name}")
            log_event("=" * 80)
        
    except Exception as e:
        log_event(f"\n❌ CRITICAL ERROR: {e}", "error")
        
        import traceback
        traceback_str = traceback.format_exc()
        log_event(f"Traceback:\n{traceback_str}", "error")
        
        try:
            if file_path.exists():
                error_path = config.ERROR_DIR / file_path.name
                file_path.rename(error_path)
                log_event(f"Moved to error directory: {error_path}", "error")
        except Exception as move_error:
            log_event(f"Failed to move file: {move_error}", "error")


def main():
    """
    Main entry point - start file watcher.
    """
    log_event("\n" + "=" * 80)
    log_event("🚀 SMART EXTRACTION PIPELINE - STARTED")
    log_event("=" * 80)
    log_event(f"📂 Monitoring: {config.QUEUE_DIR}")
    log_event(f"\n🔧 API Configuration (Two-Step Validation):")
    log_event(f"   Hypothesis:  {config.MODEL_HYPOTHESIS} (classification)")
    log_event(f"   Extraction:  {config.MODEL_CONTEXT} (big context)")
    log_event(f"   Formatting:  {config.MODEL_FORMATTER} (mechanical work)")
    log_event(f"   Validation:  {config.MODEL_VALIDATOR} (strategic insights)")
    log_event(f"\n⏳ Waiting for HTML files...")
    log_event("=" * 80)
    
    # Setup watchdog
    event_handler = HTMLFileHandler()
    observer = Observer()
    observer.schedule(event_handler, str(config.QUEUE_DIR), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log_event("\n🛑 Shutting down gracefully...")
        observer.stop()
    
    observer.join()
    log_event("👋 Pipeline stopped.")


if __name__ == "__main__":
    main()