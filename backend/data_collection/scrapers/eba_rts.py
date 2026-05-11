import time
import re
import sqlite3
import hashlib
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from ...db_init import initialize_database, get_db_name, parse_date_to_iso

URLS = [
    ("Payment services and electronic money", "https://www.eba.europa.eu/publications-and-media/publications?text=&document_type=248&media_topics=219&page=0"),
    ("Consumer protection", "https://www.eba.europa.eu/publications-and-media/publications?text=&document_type=248&media_topics=235&page=0"),
    ("AML and CFT", "https://www.eba.europa.eu/publications-and-media/publications?text=&document_type=248&media_topics=237&page=0"),
    ("Credit risk", "https://www.eba.europa.eu/publications-and-media/publications?text=&document_type=248&media_topics=234&page=0"),
    ("Digital Finance", "https://www.eba.europa.eu/publications-and-media/publications?text=&document_type=248&media_topics=5219&page=0"),
]

BASE = "https://www.eba.europa.eu"


def fetch_text(session, url, fallback):
    if not url:
        return fallback
    response = session.get(url, timeout=30)
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text('\n', strip=True)
    # Strip everything from "Documents" onwards a bit risky
    if 'Documents' in text:
        text = text[:text.index('Documents')]
    return text or fallback

def generate_unique_id(link):
    """Generate a deterministic unique ID from a link."""
    return hashlib.sha256(link.encode()).hexdigest()[:16]

def clean_text(text):
    lines = text.split('\n')
    # Drop first line if it looks like a filename
    if lines and any(x in lines[0] for x in ['%28', 'xhtml', '_EN_', '.docx']):
        lines = lines[1:]
    # Drop footer/boilerplate from "Documents" section onwards
    cutoff_phrases = ['DocumentsFinal', 'Related content', 'Press contacts', 'FooterEUROPEAN']
    result = []
    for line in lines:
        if any(phrase in line for phrase in cutoff_phrases):
            break
        result.append(line)
    lines = result
    text = '\n'.join(line.strip() for line in lines if line.strip())
    text = re.sub(r'\(\d+\)', '', text)
    text = re.sub(r'([a-z])\.([A-Z])', r'\1. \2', text)
    text = re.sub(r'([A-Z]{2,})\s+([A-Z][a-z])', r'\1\n\2', text)
    return text.rstrip()

def parse_page(html, category):
    """Parse publication list page."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".views-row")
    
    rows = []
    for card in cards:
        title_el = card.select_one("h1 a, h2 a, h3 a, h4 a")
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            continue
        
        date_el = card.find("time")
        date = date_el.get_text(strip=True) if date_el else None

        DATE_RE = re.compile(r"\b\d{1,2}\s+[A-Z][a-z]+\s+\d{4}\b")

        if not date:
            match = DATE_RE.search(card.get_text(" ", strip=True))
            date = match.group(0) if match else None
        
        doc_link = None
        url_link = None
        for a in card.find_all("a", href=True):
            text = a.get_text().lower()
            if "download" in text:
                doc_link = urljoin(BASE, a["href"])
            elif "press release" in text or "view" in text:
                url_link = urljoin(BASE, a["href"])
        
        rows.append({
            "category": category,
            "title": title,
            "published_date": date,
            "document_url": doc_link,
            "url": url_link,
        })
    
    return rows


def scrape_all(max_pages=100):
    """Scrape EBA RTS and store in SQLite."""
    db_name = get_db_name()
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    count = 0
    for topic, start_url in URLS:
        for page in range(max_pages):
            url = start_url.replace("&page=0", f"&page={page}")
            print(f"Fetching {topic} page {page}")

            r = session.get(url, timeout=30)
            rows = parse_page(r.text, topic)

            if not rows:
                break

            for row in rows:
                pk_id = generate_unique_id(row["document_url"]) if row["document_url"] else None
                text = fetch_text(session, row["url"], row["title"])
                status = 'Final' if 'final' in row["title"].lower() else 'Draft'
                
                cursor.execute("""
                    INSERT OR IGNORE INTO eba_rts 
                    (id, category, title, published_date, document_url, url, text, type, status, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pk_id,
                    row["category"],
                    row["title"],
                    parse_date_to_iso(row["published_date"]),
                    row["document_url"],
                    row["url"],
                    clean_text(text),
                    'RTS',
                    status,
                    'EBA'
                ))
                count += 1

            time.sleep(0.3)

    conn.commit()
    conn.close()
    return count


if __name__ == "__main__":
    initialize_database()
    count = scrape_all()
    print(f"✓ Stored {count} RTS in {get_db_name()}")
