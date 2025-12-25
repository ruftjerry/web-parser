import csv
import logging
from datetime import datetime
from config import LOG_FILE, CSV_LOG_FILE, PRICING

# Setup standard logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def log_event(msg: str, level: str = "info"):
    """Logs to the main text log file and prints to console."""
    print(f"[{level.upper()}] {msg}")  # Print to console
    
    if level == "info":
        logging.info(msg)
    elif level == "error":
        logging.error(msg)
    elif level == "warning":
        logging.warning(msg)

def log_token_usage(task: str, model: str, in_tok: int, out_tok: int):
    """Calculates cost and logs to CSV for cost tracking."""
    
    # Calculate Cost
    price_in = PRICING.get(model, {}).get("input", 0)
    price_out = PRICING.get(model, {}).get("output", 0)
    
    cost = ((in_tok / 1_000_000) * price_in) + ((out_tok / 1_000_000) * price_out)
    
    # Check if header needs writing
    file_exists = CSV_LOG_FILE.exists()
    
    with open(CSV_LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Task", "Model", "Input_Tokens", "Output_Tokens", "Cost_USD"])
        
        writer.writerow([
            datetime.now().isoformat(),
            task,
            model,
            in_tok,
            out_tok,
            f"${cost:.6f}"
        ])
    
    # Also log to console for immediate feedback
    log_event(f"   💰 Cost: ${cost:.4f} ({in_tok:,} in, {out_tok:,} out)")