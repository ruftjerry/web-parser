# The Pi-Catcher (Web Parser) 📥

A "Drop-and-Forget" archival engine running on a Raspberry Pi 5. It turns raw web pages into clean, permanent archives.

## The Concept

Instead of fighting anti-bot protections with scrapers, we use the **Browser** to capture the page (Visual Truth) and the **Pi** to process it (Data Truth).

1. **Capture (Mac):** You save a page using the **SingleFile** extension.
2. **Transport:** The file saves directly to a network folder (`Pi_Inbox`) monitored by the Pi.
3. **Process (Pi):** A background service detects the new file and instantly creates:
* **PDF:** A full-color, print-accurate snapshot (using Playwright).
* **Markdown:** A clean, LLM-ready text file with metadata (using BS4).



## Architecture

* **Hardware:** Raspberry Pi 5
* **Trigger:** Filesystem Watcher (`watchdog`)
* **PDF Engine:** Playwright (Headless Chromium)
* **Text Engine:** BeautifulSoup4 + Markdownify
* **Service:** Systemd (Auto-starts on boot)

## Installation

### 1. Python Environment

```bash
cd ~/projects/web-parser
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install watchdog playwright beautifulsoup4 markdownify
playwright install chromium

```

### 2. Mac Setup (The Capture Tool)

* **Extension:** Install **SingleFile** (Chrome/Edge/Safari).
* **Filename Template:** `{date-iso}_{time-iso} {page-title}`
* **Destination:** Map the `Pi_Inbox` network drive and drag it to your Finder Sidebar favorites.

### 3. The Script (`server.py`)

The script monitors `/home/pi5/Desktop/Pi_Inbox`. It ignores Mac metadata files (`._`) and auto-renames files based on the actual HTML `<title>` tag.

### 4. Service Management (Systemd)

The script runs as a background service named `web-parser`.

```bash
# Check status (Is it alive?)
sudo systemctl status web-parser

# Restart (After changing code)
sudo systemctl restart web-parser

# View Live Logs (Watch it work)
journalctl -u web-parser -f

```

## Usage

1. Navigate to any webpage (Job post, eBay listing, Article).
2. Click **SingleFile** and save to **Pi_Inbox**.
3. Check the folder in 5 seconds. You will see:
* `YYYYMMDD_HHMMSS_Page_Title.pdf`
* `YYYYMMDD_HHMMSS_Page_Title.md`
* *(Original HTML is moved to `/processed_html`)*