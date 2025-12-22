
---

# The Pi-Catcher: Research Assistant 📥

A "Drop-and-Forget" archival engine running on a Raspberry Pi 5. This tool turns messy web pages (Amazon, eBay, specialized retail) into structured, high-context Markdown research notes using LLM-powered extraction.

## 🎯 The Mission

Modern product pages and search grids are filled with "noise" (ads, trackers, related items) that make traditional scraping difficult. **The Pi-Catcher** leverages the reasoning power of an LLM to "see" what a human sees, extracting key specs and pricing from single items or complex lists.

## 🛠️ The Pipeline: Non-Destructive Parsing

The system uses a three-stage approach to ensure you never lose the original source data while gaining maximum utility:

1. **The HTML Source:** Keeps the original `SingleFile` or `PDF` for archival.
2. **The Raw Attempt:** A text-heavy extraction of the page content.
3. **The Clean Result:** The LLM-parsed Markdown file containing organized specs, prices, and summaries.

### Supported Scenarios:

* **Single Listings:** Specific items (e.g., a camera on eBay) including condition, bid amounts, and technical specs.
* **Grids/Lists:** Search result pages or category pages (e.g., Micro Center CPU lists) converted into clean Markdown tables.
* **Research Areas:** Audio gear, photography equipment, computer hardware, and individual company product pages.

---

## 📂 Project Structure

```text
/home/pi5/projects/web-parser
│
├── Pi_Inbox/                     <-- THE HOT FOLDER (Map this to your Mac/PC)
│   ├── Research_Queue/           <-- Drop SingleFile HTML or PDFs here
│   └── Processed_Archive/        <-- Completed runs (grouped by date/item)
│
├── Scripts/
│   ├── folder_watcher.py         <-- The Traffic Cop (Monitors the Inbox)
│   ├── research_assistant.py     <-- Logic: Sends context to LLM & parses MD
│   └── utils.py                  <-- Cleaning & file handling helpers
│
├── venv/                         <-- Python Virtual Environment
├── requirements.txt              <-- Dependencies (Watchdog, OpenAI/Anthropic)
└── README.md

```

---

## ⚙️ Architecture

* **Hardware:** Raspberry Pi 5 (Optimized for 24/7 background processing).
* **Trigger:** `watchdog` (Filesystem Event Handler).
* **Extraction Engine:** LLM-based (GPT-4o or Claude 3.5 Sonnet) to handle unpredictable web layouts.
* **Capture Source:** **SingleFile** Browser Extension (preferred for HTML context) or **Print to PDF**.

---

## 🚀 Installation & Setup

### 1. Python Environment

```bash
cd ~/projects/web-parser
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install watchdog beautifulsoup4 markdownify openai

```

### 2. Configure the Watcher

Update `Scripts/folder_watcher.py` to point to your Raspberry Pi's network-attached storage or local folder.

### 3. Service Management (Systemd)

The parser runs as a background service so it's always ready when you save a file.

```bash
# Check if the service is running
sudo systemctl status web-parser

# Restart after updating the LLM prompt
sudo systemctl restart web-parser

# Watch the live logs as you drop files
journalctl -u web-parser -f

```

---

## 🖥️ Usage

1. **Capture:** Use **SingleFile** to save a product page (e.g., a vintage lens on eBay).
2. **Drop:** Move that file into the `Pi_Inbox/Research_Queue` folder.
3. **Analyze:** The Pi-Catcher detects the file, sends the text to the LLM, and creates a folder in `Processed_Archive` containing:
* `source.html` (The original file).
* `research_notes.md` (The clean, structured data).



---

## 🛠️ Development Focus

* **`research_assistant.py`**: This is where the Prompt Engineering lives. It instructs the LLM to identify if the page is a **Single Item** or a **List/Grid** and format the output accordingly.
* **Data Integrity**: The script ensures no data is deleted. If an LLM call fails, the raw HTML remains safe in the inbox for a retry.

---