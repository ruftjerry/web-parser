import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
INBOX_DIR = BASE_DIR / "Pi_Inbox"

QUEUE_DIR = INBOX_DIR / "Research_Queue"
ARCHIVE_DIR = INBOX_DIR / "Processed_Archive"
ERROR_DIR = INBOX_DIR / "Errors"
OUTPUT_DIR = INBOX_DIR / "Output" 

LOG_FILE = BASE_DIR / "research_pipeline.log"
CSV_LOG_FILE = BASE_DIR / "token_usage_log.csv"
CACHE_FILE = BASE_DIR / "fingerprint_cache.json"

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env file")

# --- Model Strategies ---
# Using gpt-4o-mini for context analysis to stay within rate limits
# Your account: gpt-4o = 30K TPM, gpt-4o-mini = 200K TPM
# Large HTML files (100KB+) exceed gpt-4o limits but fit in gpt-4o-mini
MODEL_SMART = "gpt-4o-mini"      # Context Analysis (needs high token limit)
MODEL_VERIFY = "gpt-4o"          # Verification (small payload, wants quality)
MODEL_FAST = "gpt-4o-mini"       # Technical Planning

PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60}
}

# --- Fingerprint Cache Settings ---
CACHE_MIN_SUCCESS_RATE = 0.85  # Only use cached plans with >85% success rate
CACHE_STALENESS_DAYS = 30      # Re-analyze if plan hasn't been used in 30 days

# --- System Settings ---
NETWORK_STABILIZATION_TIME = 2.0