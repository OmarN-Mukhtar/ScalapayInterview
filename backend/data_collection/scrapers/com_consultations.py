import sqlite3
import time
import requests
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup

from ...db_init import (
    initialize_database,
    get_db_name,
    generate_id_from_link,
    parse_date_to_iso,
)

initialize_database()
DB_NAME = get_db_name()

RSS_FEED_URL = "https://finance.ec.europa.eu/node/1066/rss_en"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36"
    )
}


def fetch_rss_feed(url):
    return feedparser.parse(url)


def extract_metadata(entry):
    tags = entry.get("tags", []) or []

    return {"id": entry.get("id", entry.get("link", "")),
        "title": entry.get("title", ""),
        "description": entry.get("summary", ""),
        "link": entry.get("link", ""),
        "published_date": entry.get("published", ""),
        "tags": ",".join(tag.get("term", "") for tag in tags),
        "category": tags[0].get("term") if tags else "general",}


def get_keyword_filters():
    return {"payment_services": ["PSD2", "PSD3", "PSR", "settlement", "authorisation", "payment services"],
        "bnpl_credit": ["BNPL", "consumer credit", "CCD2", "responsible lending","consumer credit directive"],
        "aml_cft": ["AML", "CFT", "AMLD6", "transfer of funds", "TFR", "travel rule","EBA AML", "money laundering"],
        "operational_resilience": ["DORA", "digital operational resilience", "operational resilience"],
        "data_ai": ["GDPR", "AI Act", "artificial intelligence", "data protection","credit decisioning", "fraud model"],}


def matches_filter(title, description, filters):
    text = f"{title} {description}".lower()
    matches = []

    for category, keywords in filters.items():
        if any(keyword.lower() in text for keyword in keywords):
            matches.append(category)

    return matches


def normalize_text(text):
    return " ".join(text.split()) if text else ""


def clean_text_from_html(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "nav", "header", "footer",
        "svg", "button", "form", "highcharts-chart"]):
        tag.decompose() # remove unwanted tags

    main = (
        soup.select_one("main#main-content") or
        soup.select_one("#ecl-main-content") or
        soup.select_one("app-root") or
        soup.body or
        soup
    )

    text = main.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    return "\n".join(lines) if lines else None


def fetch_rendered_html(url):
    """
    Fetch HTML. If the page is an Angular shell with little content,
    render it with Playwright.
    """
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    html = response.text
    text = clean_text_from_html(html)

    if text and len(text) > 500:
        return html

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
            browser.close()

        return html

    except Exception:
        return html


def split_date_range(text):
    text = normalize_text(text)

    if " - " not in text:
        return None, None

    start, end = text.split(" - ", 1)

    # Remove extra notes like "(midnight Brussels time)"
    end = end.split("(")[0].strip()

    return start.strip(), end.strip()

def extract_details_from_html(html):
    details = {"status": None,
        "opening_date": None,
        "deadline_date": None,}

    soup = BeautifulSoup(html, "html.parser")

    for dt in soup.find_all("dt", class_="ecl-description-list__term"):
        term = normalize_text(dt.get_text(" ", strip=True)).lower()
        dd = dt.find_next_sibling("dd", class_="ecl-description-list__definition")

        if not dd:
            continue

        value = normalize_text(dd.get_text(" ", strip=True))
        time_tag = dd.find("time")
        datetime_value = time_tag.get("datetime") if time_tag else None

        if "status" in term:
            details["status"] = value

        elif "opening" in term:
            details["opening_date"] = datetime_value or value

        elif "deadline" in term:
            details["deadline_date"] = datetime_value or value

        elif "consultation period" in term:
            start, end = split_date_range(value)
            details["opening_date"] = details["opening_date"] or start
            details["deadline_date"] = details["deadline_date"] or end

    page_text = normalize_text(soup.get_text(" ", strip=True)).lower()

    if not details["status"] and (
        "response period for this consultation has ended" in page_text or
        "questionnaire is no longer available" in page_text
    ):
        details["status"] = "Closed"

    details["opening_date"] = parse_date_to_iso(details["opening_date"])
    details["deadline_date"] = parse_date_to_iso(details["deadline_date"])

    return details


def fetch_consultation_page(url):
    html = fetch_rendered_html(url)

    return {
        "details": extract_details_from_html(html),
        "text": clean_text_from_html(html),
    }


def store_consultations(feed):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    filters = get_keyword_filters()
    stored = 0
    skipped = 0
    
    for entry in feed.entries:
        metadata = extract_metadata(entry)
        matched_categories = matches_filter(
            metadata["title"],
            metadata["description"],
            filters,
        )
        
        if not matched_categories:
            skipped += 1
            continue
        
        # Fetch details immediately
        page = fetch_consultation_page(metadata["link"])
        details = page["details"]
        text = page["text"]
        
        pk_id = generate_id_from_link(metadata["link"])
        
        cursor.execute("""
            INSERT OR REPLACE INTO com_consultations
            (id, url, title, description, published_date, type, category,
             status, opening_date, deadline_date, text, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pk_id,
            metadata["link"],
            metadata["title"],
            metadata["description"],
            parse_date_to_iso(metadata["published_date"]),
            "Public Consultation",
            ",".join(matched_categories),
            details["status"],
            details["opening_date"],
            details["deadline_date"],
            text,
            "European Commission",
        ))
        
        stored += 1
        time.sleep(1)
    
    conn.commit()
    conn.close()
    return stored, skipped


def main():
    feed = fetch_rss_feed(RSS_FEED_URL)

    if not feed.entries:
        print("No RSS entries found.")
        return

    stored, skipped = store_consultations(feed)

    print(
        f"Done. RSS entries: {len(feed.entries)} | "
        f"stored: {stored} | skipped: {skipped} | "
    )


if __name__ == "__main__":
    main()
