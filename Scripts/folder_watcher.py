import time
import subprocess
import threading
import queue
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- CONFIGURATION ---
RESEARCH_SCRIPT = "/home/pi5/projects/web-parser/Scripts/research_assistant.py"
PYTHON_EXEC = "/home/pi5/projects/web-parser/venv/bin/python3"
WATCH_DIR = "/home/pi5/projects/web-parser/Pi_Inbox/Research_Queue"

COOLDOWN_SECONDS = 1.0          # Delay before processing starts
DEBOUNCE_SECONDS = 60.0         # Ignore repeat events for this long (increased for safety)
STABILIZE_CHECKS = 12           # How many times to check file size
STABILIZE_DELAY = 0.5           # Seconds between checks

# Thread-safe queue
processing_queue = queue.Queue()

# In-memory debounce cache
_recent = {}

def wait_for_stable_file(path: Path) -> bool:
    """
    Waits for file size to stop changing. 
    Returns True if stable and exists, False if it vanishes.
    """
    last_size = -1
    for _ in range(STABILIZE_CHECKS):
        if not path.exists():
            time.sleep(STABILIZE_DELAY)
            continue
            
        try:
            current_size = path.stat().st_size
        except FileNotFoundError:
            time.sleep(STABILIZE_DELAY)
            continue

        if current_size == last_size and current_size > 0:
            return True
        
        last_size = current_size
        time.sleep(STABILIZE_DELAY)
        
    return path.exists()

def should_process(path: Path) -> bool:
    """Debounce: ensure we only process a specific path once per window."""
    now = time.time()
    key = str(path)
    last_time = _recent.get(key, 0)
    
    # If we saw this file recently, ignore it
    if now - last_time < DEBOUNCE_SECONDS:
        return False
        
    _recent[key] = now
    return True

def is_target_file(path: Path) -> bool:
    if path.name.startswith("."):
        return False
    return path.suffix.lower() in [".html", ".pdf"]

def run_parser(file_path: Path):
    """Runs the external python script."""
    print(f"🚀 Starting parser for: {file_path.name}")
    try:
        result = subprocess.run(
            [PYTHON_EXEC, RESEARCH_SCRIPT, str(file_path)],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"✅ Processed successfully: {file_path.name}")
        else:
            print(f"❌ Parser Error for {file_path.name}")
            print(f"Stderr: {result.stderr.strip()}")

    except Exception as e:
        print(f"❌ Execution failed: {e}")

def worker():
    """
    Consumer thread: pulls files from queue and processes them sequentially.
    """
    while True:
        path = processing_queue.get()
        try:
            # Double-check existence before starting work (in case it was moved)
            if not path.exists():
                print(f"⚠️ Skipping (file gone): {path.name}")
                continue

            print(f"✨ New file detected: {path.name}")
            
            # Wait for stabilization
            if wait_for_stable_file(path):
                time.sleep(COOLDOWN_SECONDS)
                run_parser(path)
            else:
                print(f"⚠️ File unstable or moved: {path.name}")
                
        except Exception as e:
            print(f"💥 Worker error: {e}")
        finally:
            processing_queue.task_done()

class ResearchHandler(FileSystemEventHandler):
    """
    Handler now filters duplicates (debounce) BEFORE queuing.
    This prevents 'echo' events from clogging the queue while the worker is busy.
    """
    def _queue_path(self, path: Path):
        if not is_target_file(path):
            return

        # FILTER HERE: If we just queued this file, don't queue it again.
        if should_process(path):
            processing_queue.put(path)

    def on_created(self, event):
        if not event.is_directory:
            self._queue_path(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            self._queue_path(Path(event.dest_path))

if __name__ == "__main__":
    Path(WATCH_DIR).mkdir(parents=True, exist_ok=True)

    # 1. Start the worker thread
    processing_thread = threading.Thread(target=worker, daemon=True)
    processing_thread.start()

    # 2. Start the Watchdog
    event_handler = ResearchHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=False)

    print(f"🛰️ Pi-Catcher is standing by in: {WATCH_DIR}")
    print("Press Ctrl+C to stop.")

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()