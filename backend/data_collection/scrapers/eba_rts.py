import re
import time
import sqlite3
import hashlib
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup
from backend.db_init import initialize_database, get_db_name, parse_date_to_iso

URLS = [
    ("Payment services and electronic money", "https://www.eba.europa.eu/publications-and-media/publications?text=&document_type=248&media_topics=219&page=0"),
    ("Consumer protection", "https://www.eba.europa.eu/publications-and-media/publications?text=&document_type=248&media_topics=235&page=0"),
    ("AML and CFT", "https://www.eba.europa.eu/publications-and-media/publications?text=&document_type=248&media_topics=237&page=0"),
    ("Credit risk", "https://www.eba.europa.eu/publications-and-media/publications?text=&document_type=248&media_topics=234&page=0"),
    ("Digital Finance", "https://www.eba.europa.eu/publications-and-media/publications?text=&document_type=248&media_topics=5219&page=0"),
]

BASE = "https://www.eba.europa.eu"
DATE_RE = re.compile(r"\b\d{1,2}\s+[A-Z][a-z]+\s+\d{4}\b")


def clean(x):
    return re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip() if x else ""


def parse_text_from_url(session, url, fallback_title):
    """Fetch a URL and parse readable page text. Fall back to title if no URL exists or parsing fails."""
    if not url:
        return fallback_title

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Could not fetch text URL {url}: {exc}")
        return fallback_title

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove non-content elements before extracting text.
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    # Prefer likely article/content containers, then fall back to the whole body.
    content = soup.select_one("main, article, .region-content, .main-content, .content, #content")
    text = clean(content) if content else clean(soup.body or soup)

    return text or fallback_title


def ensure_text_column(cursor):
    """Add text column if the current eba_rts schema does not already have it."""
    cursor.execute("PRAGMA table_info(eba_rts)")
    columns = {row[1] for row in cursor.fetchall()}

    if "text" not in columns:
        cursor.execute("ALTER TABLE eba_rts ADD COLUMN text TEXT")


def set_page(url, page):
    parts = urlparse(url)
    query = parse_qs(parts.query)
    query["page"] = [str(page)]
    return urlunparse(parts._replace(query=urlencode(query, doseq=True)))


def find_link(card, label):
    label = label.lower()
    for a in card.find_all("a", href=True):
        if label in clean(a).lower():
            return urljoin(BASE, a["href"])
    return None


def parse_page(html, category):
    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select(".views-row")

    if not cards:
        cards = [
            el for el in soup.select("article, li, div")
            if "Download document" in clean(el)
        ]

    rows = []

    for card in cards:
        text = clean(card)

        if "Download document" not in text:
            continue

        title_el = card.select_one("h1 a, h2 a, h3 a, h4 a")
        title = clean(title_el)

        if not title:
            continue

        date_el = card.find("time")
        date = clean(date_el)

        if not date:
            match = DATE_RE.search(text)
            date = match.group(0) if match else None

        rows.append({
            "category": category,
            "title": title,
            "published_date": date,
            "document_url": find_link(card, "Download document"),
            "url": find_link(card, "View press release"),
        })

    return rows


def generate_unique_id(link):
    """Generate a deterministic unique ID from a link"""
    return hashlib.sha256(link.encode()).hexdigest()[:16]


def determine_status(title):
    """Determine status based on title. Set to 'Final' if 'final' is in title (case-insensitive)"""
    if 'final' in title.lower():
        return 'Final'
    return 'Draft'


def scrape_all(max_pages=100):
    """Scrape EBA publications and store directly in SQLite database"""
    db_name = get_db_name()
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    ensure_text_column(cursor)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0"
    })

    total_inserted = 0
    total_skipped = 0
    seen = set()

    for topic, start_url in URLS:
        for page in range(max_pages):
            url = set_page(start_url, page)
            print(f"Fetching {topic} page {page}")

            r = session.get(url, timeout=30)
            r.raise_for_status()

            rows = parse_page(r.text, topic)

            if not rows:
                break

            new_count = 0

            for row in rows:
                key = (
                    row["category"],
                    row["title"],
                    row["published_date"],
                    row["document_url"],
                    row["url"],
                )

                if key not in seen:
                    seen.add(key)
                    
                    # Generate unique ID from document link
                    pk_id = generate_unique_id(row["document_url"]) if row["document_url"] else None
                    parsed_text = parse_text_from_url(session, row["url"], row["title"])
                    status = determine_status(row["title"])
                    
                    try:
                        cursor.execute("""
                            INSERT INTO eba_rts 
                            (id, category, title, published_date, document_url, url, text, type, status, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            pk_id,
                            row["category"],
                            row["title"],
                            parse_date_to_iso(row["published_date"]),
                            row["document_url"],
                            row["url"],
                            parsed_text,
                            'RTS',
                            status,
                            'EBA'
                        ))
                        total_inserted += 1
                        new_count += 1
                    except sqlite3.IntegrityError:
                        total_skipped += 1

            if new_count == 0:
                break

            time.sleep(0.3)

    conn.commit()
    conn.close()
    
    return total_inserted, total_skipped


if __name__ == "__main__":
    # Initialize database schema first
    initialize_database()
    db_name = get_db_name()
    
    inserted, skipped = scrape_all()
    print(f"✓ Inserted {inserted} new publications")
    print(f"✓ Skipped {skipped} duplicate entries")
    print(f"✓ Data stored in {db_name}")
