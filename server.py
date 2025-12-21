import os
import time
import re
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# --- CONFIGURATION ---
WATCH_FOLDER = "/home/pi5/Desktop/Pi_Inbox"
PROCESSED_FOLDER = os.path.join(WATCH_FOLDER, "processed_html")

def clean_filename(text):
    if not text: return "Untitled"
    clean = re.sub(r'[^\w\s-]', '', text).strip()
    return re.sub(r'[-\s]+', '_', clean)[:60]

def clean_junk(soup):
    for tag in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript", "svg", "button", "input", "form", "link"]):
        tag.decompose()
        
    junk_headers = ["Similar Items", "Sponsored", "Related searches", "You may also like", "Footer", "Reviews", "More to explore", "Filter"]
    for header in soup.find_all(re.compile('^h[1-6]$')):
        if any(junk in header.get_text(strip=True) for junk in junk_headers):
            parent = header.find_parent('div')
            if parent: parent.decompose()
            else: header.decompose()
    return soup

def extract_url_from_html(content):
    # SingleFile adds a comment like: # Or sometimes just text at the top. We look for "Saved from url".
    match = re.search(r"Saved from url=\(\d+\)(https?://\S+)", content)
    if match:
        return match.group(1)
    
    # Fallback: Look for standard canonical link
    soup = BeautifulSoup(content, "html.parser")
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        return canonical["href"]
        
    return ""

class InboxHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory: return
        filename = os.path.basename(event.src_path)
        if filename.startswith("._"): return
        if filename.endswith(".html"):
            print(f"\n👀 Detected: {filename}")
            time.sleep(2) 
            self.process_file(event.src_path)

    def process_file(self, filepath):
        try:
            # 1. READ CONTENT
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
                
            soup = BeautifulSoup(html_content, "html.parser")
            
            page_title = soup.title.string.strip() if (soup.title and soup.title.string) else "Untitled"
            source_url = extract_url_from_html(html_content)
            
            # --- TIMESTAMP & FILENAME ---
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            safe_title = clean_filename(page_title)
            new_base_name = f"{timestamp}_{safe_title}"
            
            print(f"   🏷️  Renaming to: {new_base_name}")

            # 2. PDF (Visual)
            pdf_path = os.path.join(WATCH_FOLDER, f"{new_base_name}.pdf")
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(f"file://{os.path.abspath(filepath)}")
                page.emulate_media(media="screen")
                page.pdf(
                    path=pdf_path, 
                    format="Letter", 
                    margin={"top": "0.5in", "bottom": "0.5in", "left": "0.5in", "right": "0.5in"},
                    print_background=True
                )
                browser.close()
            print(f"   📄 PDF Created")

            # 3. MARKDOWN (Data)
            soup = clean_junk(soup)
            markdown_text = md(str(soup), heading_style="ATX", strip=['a', 'img', 'span'])
            markdown_text = re.sub(r'\n\s*\n', '\n\n', markdown_text).strip()

            # --- SMART FRONTMATTER ---
            frontmatter = (
                f"---\n"
                f"date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"title: \"{page_title}\"\n"
                f"source_url: {source_url}\n"
                f"tags: [inbox]\n"
                f"---\n\n"
            )
            
            md_path = os.path.join(WATCH_FOLDER, f"{new_base_name}.md")
            with open(md_path, "w") as f:
                f.write(frontmatter + markdown_text)
            print(f"   📝 Markdown Created")

            # 4. CLEANUP
            os.makedirs(PROCESSED_FOLDER, exist_ok=True)
            shutil.move(filepath, os.path.join(PROCESSED_FOLDER, os.path.basename(filepath)))
            print(f"   🧹 Cleanup Done")
            print(f"✅ SUCCESS")

        except Exception as e:
            print(f"❌ Error processing {filepath}: {e}")

if __name__ == "__main__":
    observer = Observer()
    handler = InboxHandler()
    observer.schedule(handler, WATCH_FOLDER, recursive=False)
    print(f"🚀 Pi Watcher Active")
    observer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: observer.stop()
    observer.join()