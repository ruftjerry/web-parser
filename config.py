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

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLEAISTUDIO_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env file")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLEAISTUDIO_API_KEY not found in .env file")

# --- Model Strategies (TWO-STEP VALIDATION) ---
# Step 1: Hypothesis - mini classifies page type (fast & cheap)
# Step 2: Extraction - Gemini extracts with massive context window
# Step 3A: Formatting - mini converts JSON to markdown (mechanical work)
# Step 3B: Validation - 4o reviews and adds insights (strategic oversight)

MODEL_HYPOTHESIS = "gpt-4o-mini"        # OpenAI - cheap classification
MODEL_CONTEXT = "gemini-2.5-flash"      # Google - 1M token window
MODEL_FORMATTER = "gpt-4o-mini"         # OpenAI - mechanical formatting
MODEL_VALIDATOR = "gpt-4o"              # OpenAI - strategic validation

PRICING = {
    # OpenAI pricing (per 1M tokens)
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    
    # Google Gemini pricing (per 1M tokens)
    # Source: https://ai.google.dev/pricing
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gemini-flash-latest": {"input": 0.075, "output": 0.30}
}

# --- System Settings ---
NETWORK_STABILIZATION_TIME = 2.0