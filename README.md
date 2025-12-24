Here is the updated `README.md`. It reflects the shift to the **Hybrid Model Strategy**, the **PDF-centric workflow**, and the new **Cost Tracking** features we implemented.

---

# The Pi-Catcher: Hybrid Research Assistant 📥

A "Drop-and-Forget" archival engine running on a Raspberry Pi 5. This tool turns messy PDFs (saved web pages, spec sheets, invoices) into structured, high-context Markdown research notes using a **Hybrid AI Strategy**.

## 🎯 The Mission

Modern product research involves hundreds of tabs and messy documents. **The Pi-Catcher** acts as a tireless research assistant. It uses a "Smart/Fast" model architecture to read documents, identifying key specs, pricing, and compatibility details while filtering out ads and SEO noise.

It is specifically primed for a "Technical Researcher" persona, prioritizing long-term value and technical trade-offs over marketing fluff.

---

## 🧠 The "Hybrid" Engine (High IQ, Low Cost)

To balance intelligence and cost, the system utilizes a multi-phase approach using different OpenAI models:

1. **Phase 1: Triage (GPT-4o)**
* **Role:** The "Brain." It reads the first page to understand the document type (Invoice vs. Catalog), domain (Audio, PC, Photo), and extraction strategy.


2. **Phase 2: Extraction (GPT-4o-mini)**
* **Role:** The "Workhorse." Runs in parallel across the document using a sliding-window technique to extract raw item data cheaply and quickly.


3. **Phase 3: Filtering (GPT-4o-mini)**
* **Role:** The "Auditor." Scrubs the data, tagging accessories, parts-only items, and removing navigation noise.


4. **Phase 4: Summary (GPT-4o)**
* **Role:** The "Analyst." Writes a high-level executive summary and insights based on the clean data.



**Result:** High-quality analysis for ~$0.01 per document.

---

## 📂 Project Structure

```text
/home/pi5/projects/web-parser
│
├── Pi_Inbox/                     <-- THE HOT FOLDER (Network Share)
│   ├── Research_Queue/           <-- Drop PDFs here
│   └── Processed_Archive/        <-- Completed runs (MD + JSON + PDF)
│
├── Scripts/
│   ├── folder_watcher.py         <-- Monitors the Inbox
│   ├── research_assistant.py     <-- The Hybrid AI Engine
│   ├── token_usage_log.csv       <-- Real-time cost & usage tracking
│   └── utils.py                  <-- File helpers
│
├── venv/                         <-- Python Virtual Environment
├── requirements.txt              <-- Dependencies
└── README.md

```

---

## ⚙️ Architecture & Features

* **Hardware:** Raspberry Pi 5 (Optimized for concurrent processing).
* **Concurrency:** Uses `ThreadPoolExecutor` with **Thread-Local Storage** to safely manage API connections across multiple CPU cores.
* **PDF Engine:** Uses `PyMuPDF` with a "Sliding Window" (overlapping context) to ensure data isn't lost between page breaks.
* **Cost Tracking:** Automatically appends every API call to `token_usage_log.csv` with timestamp, model used, tokens, and estimated USD cost.
* **Deduplication:** Robust "Fingerprinting" logic that combines Hard IDs (SKU, URL) with Fuzzy Matching (Name + Price Bucket + Seller) to merge duplicates.

---

## 🚀 Installation & Setup

### 1. Python Environment

```bash
cd ~/projects/web-parser
python3 -m venv venv
source venv/bin/activate

# Install dependencies (Updated for PDF & AI support)
pip install watchdog openai pymupdf

```

### 2. Configuration

Ensure your `OPENAI_API_KEY` is set in your environment variables.
You can adjust the "Smart" and "Fast" models inside `research_assistant.py` if needed.

### 3. Service Management

The parser runs as a background service via systemd.

```bash
# Check status
sudo systemctl status web-parser

# Watch live logs (including cost estimates)
journalctl -u web-parser -f

```

---

## 🖥️ Usage

1. **Capture:** "Print to PDF" on any product page, search result, or technical spec sheet.
2. **Drop:** Save the file to `Pi_Inbox/Research_Queue`.
3. **Forget:** The system detects the file and processes it in the background.
4. **Review:** Open `Processed_Archive`. You will find:
* `[Date]_[Name]_report.md`: The human-readable research note.
* `[Date]_[Name]_data.json`: The raw structured data for database ingestion.
* `[Date]_[Name]_source.pdf`: The archived original file.



### Monitoring Costs

To see how much you are spending on research, simply cat the log:

```bash
tail -f Scripts/token_usage_log.csv

```

---

## 🛠️ Development Focus

* **`research_assistant.py`**: Contains the **System Primer** (User Persona) and the Hybrid Logic.
* **Thread Safety**: Critical for the Pi 5. Logging uses `threading.Lock()` and API calls use thread-local clients to prevent race conditions.