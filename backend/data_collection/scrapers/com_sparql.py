import io
import re
import sqlite3
import zipfile

import requests
import time
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin
from backend.db_init import initialize_database, get_db_name, generate_unique_id, parse_date_to_iso

from bs4 import XMLParsedAsHTMLWarning
import warnings
import os

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
# Initialize unified database
initialize_database()
DB_NAME = get_db_name()

# SPARQL Endpoint
SPARQL_ENDPOINT = "http://publications.europa.eu/webapi/rdf/sparql"

# Query file
QUERY_FILE_LOCATIONS = [
    "backend/data_collection/queries/com_queries.rq",
]

def get_query_file_path():
    """Find the query file in available locations"""
    return QUERY_FILE_LOCATIONS[0]

def read_sparql_query(filename):
    """Read SPARQL query from file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: {filename} not found")
        return None


# CELLAR download headers
CELLAR_ACCEPT_HEADERS = {
    'Accept': (
        'application/xhtml+xml, text/html, text/html;type=simplified, '
        'application/zip;mtype=fmx4, application/xml;mtype=fmx4, '
        'application/xml;notice=object, text/plain'
    ),
    'Accept-Language': 'eng',
}


def ensure_text_column(cursor):
    """Make sure com_proposals has a text column for extracted document text."""
    cursor.execute("PRAGMA table_info(com_proposals)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'text' not in columns:
        cursor.execute('ALTER TABLE com_proposals ADD COLUMN text TEXT')


def clean_text(raw_text):
    """Normalize whitespace and remove common EU wrapper noise."""
    if not raw_text:
        return ''

    text = raw_text.replace('\u00a0', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+([\.,;:])', r'\1', text)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    return text.strip()


def is_noise_piece(piece):
    """Skip wrapper/navigation fragments, not legal content."""
    if not piece:
        return True
    normalized = clean_text(piece)
    lowered = normalized.lower()
    if lowered in {'important legal notice', '[pic]', 'pic'}:
        return True
    if lowered.startswith("list of uri") or lowered.startswith("list of uri's"):
        return True
    if lowered.startswith('cellar:'):
        return True
    if re.fullmatch(r'https?://\S+', lowered):
        return True
    return False


def dedupe_pieces(pieces):
    """Preserve order while removing exact paragraph/table duplicates."""
    seen = set()
    cleaned = []
    for piece in pieces:
        piece = clean_text(piece)
        if is_noise_piece(piece):
            continue
        key = re.sub(r'\W+', '', piece).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(piece)
    return cleaned


def html_to_text(html):
    """Extract readable text from EU HTML/XHTML content."""
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup(['script', 'style', 'head', 'nav', 'noscript']):
        tag.decompose()

    root = soup.body or soup
    pieces = []

    for tag in root.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'tr'], recursive=True):
        # Avoid extracting the same table content twice from nested p/li inside rows.
        if tag.name != 'tr' and tag.find_parent('tr'):
            continue

        if tag.name == 'tr':
            cells = [cell.get_text(' ', strip=True) for cell in tag.find_all(['th', 'td'])]
            text = ' | '.join(cell for cell in cells if cell)
        else:
            text = tag.get_text(' ', strip=True)

        if text:
            pieces.append(text)

    pieces = dedupe_pieces(pieces)
    if pieces:
        return clean_text('\n\n'.join(pieces))

    # Fallback for unusually flat pages.
    return clean_text(root.get_text('\n', strip=True))


def xml_to_text(xml):
    """Extract text from EU XML, skipping footnotes where marked."""
    soup = BeautifulSoup(xml, 'lxml-xml')
    root = soup.find()

    if root and root.name and root.name.lower() == 'html':
        return html_to_text(xml)

    for tag in soup.find_all(lambda t: (t.get('TYPE') or t.get('type') or '').upper() == 'FOOTNOTE'):
        tag.decompose()

    pieces = []
    wanted = ['TITLE', 'TI', 'P', 'PARAG', 'ALINEA', 'POINT', 'RECITAL', 'ARTICLE', 'ROW']
    for tag in soup.find_all(wanted):
        if tag.find_parent(wanted):
            continue
        text = tag.get_text(' ', strip=True)
        if text:
            pieces.append(text)

    pieces = dedupe_pieces(pieces)
    if pieces:
        return clean_text('\n\n'.join(pieces))

    return clean_text(soup.get_text(' ', strip=True))


def extract_text_from_bytes(content, filename='', content_type=''):
    """Choose the XML or HTML extractor for a downloaded CELLAR file."""
    text = content.decode('utf-8', errors='replace')
    filename = filename.lower()
    content_type = content_type.lower()

    if filename.endswith(('.html', '.xhtml')) or 'html' in content_type:
        return html_to_text(text)
    if filename.endswith('.xml') or 'xml' in content_type:
        return xml_to_text(text)
    return clean_text(text)


def extract_doc_links(html, base_url):
    """Find real /DOC_* resources from CELLAR URI-list pages."""
    soup = BeautifulSoup(html, 'lxml')
    links = []
    for anchor in soup.find_all('a', href=True):
        href = urljoin(base_url, anchor['href'])
        href_lc = href.lower()
        if '/resource/cellar/' not in href_lc or '/doc_' not in href_lc:
            continue
        if not any(ext in href_lc for ext in ('.html', '.xhtml', '.xml', '/doc_')):
            continue
        links.append(href)

    # Prefer readable HTML/XHTML variants when there are duplicate links for the same DOC_*.
    best_by_doc = {}
    for link in links:
        match = re.search(r'/DOC_([^/?#]+)', link, re.IGNORECASE)
        key = match.group(1).lower() if match else link.lower()
        current = best_by_doc.get(key)
        if not current or rank_doc_link(link) < rank_doc_link(current):
            best_by_doc[key] = link

    return list(dict.fromkeys(best_by_doc.values()))


def rank_doc_link(link):
    """Lower score is better: English HTML before XML/plain alternatives."""
    lowered = link.lower()
    score = 0
    if '.html' in lowered or '.xhtml' in lowered:
        score -= 20
    if '.xml' in lowered:
        score -= 5
    if '_en_' in lowered or '/eng' in lowered:
        score -= 5
    if 'annex' in lowered or 'annexe' in lowered:
        score += 2
    return score


def merge_unique_texts(texts):
    """Join downloaded parts while dropping duplicate representations."""
    merged = []
    fingerprints = set()
    for text in texts:
        text = clean_text(text)
        if not text:
            continue
        fingerprint = re.sub(r'\W+', '', text).lower()
        if not fingerprint:
            continue
        short_fp = fingerprint[:12000]
        if short_fp in fingerprints:
            continue
        fingerprints.add(short_fp)
        merged.append(text)
    return '\n\n'.join(merged).strip()


def extract_zip_text(content):
    """Extract the best readable XML/HTML candidates from a CELLAR ZIP."""
    candidates = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for name in archive.namelist():
            lower_name = name.lower()
            if not lower_name.endswith(('.html', '.xhtml', '.xml')):
                continue
            if 'toc' in lower_name or 'table_of_contents' in lower_name:
                continue
            candidates.append(name)

        # If HTML/XHTML is present, prefer it over XML to avoid duplicate text.
        html_candidates = [name for name in candidates if name.lower().endswith(('.html', '.xhtml'))]
        selected = html_candidates or candidates
        selected.sort(key=rank_doc_link)

        texts = [extract_text_from_bytes(archive.read(name), name) for name in selected]

    return merge_unique_texts(texts)


def fetch_url_text(url, depth=0):
    """Download one CELLAR URL, following URI-list pages to actual DOC_* resources."""
    if depth > 2:
        return ''

    try:
        response = requests.get(url, headers=CELLAR_ACCEPT_HEADERS, timeout=60)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error downloading CELLAR text for {url}: {e}")
        return ''

    content_type = response.headers.get('Content-Type', '').lower()

    if 'zip' in content_type or response.content.startswith(b'PK'):
        try:
            return extract_zip_text(response.content)
        except zipfile.BadZipFile as e:
            print(f"Error reading ZIP for {url}: {e}")
            return ''

    body = response.content.decode('utf-8', errors='replace')
    if 'html' in content_type or '<html' in body[:1000].lower():
        doc_links = extract_doc_links(body, response.url)
        page_text = html_to_text(body)

        # CELLAR sometimes returns a URI-list page. Follow the listed DOC_* links instead.
        if doc_links and ('list of uri' in page_text.lower() or len(page_text) < 2000):
            return merge_unique_texts(fetch_url_text(link, depth + 1) for link in doc_links)

        return page_text

    return extract_text_from_bytes(response.content, url, content_type)


def fetch_document_text(doc):
    """Download a CELLAR resource and return readable document text."""
    cellar_id = (doc.get('cellar_id') or '').strip()
    if not cellar_id and doc.get('url'):
        cellar_id = doc['url'].rstrip('/').split('/')[-1]

    if cellar_id:
        url = f'http://publications.europa.eu/resource/cellar/{cellar_id}'
    else:
        url = doc.get('url', '')

    if not url:
        return ''

    return fetch_url_text(url)

def execute_sparql_query(endpoint, query):
    """Execute SPARQL query and return results"""
    print(f"Executing SPARQL query against {endpoint}...")
    
    headers = {
        'Accept': 'application/sparql-results+json',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'query': query
    }
    
    try:
        response = requests.post(endpoint, headers=headers, data=data, timeout=60)
        response.raise_for_status()
        results = response.json()
        return results
    except requests.exceptions.RequestException as e:
        print(f"Error querying SPARQL endpoint: {e}")
        return None

def parse_sparql_results(results):
    """Parse SPARQL JSON results into list of proposals"""
    documents = []
    
    if not results or 'results' not in results or 'bindings' not in results['results']:
        print("No results found in SPARQL response")
        return documents
    
    bindings = results['results']['bindings']
    print(f"Found {len(bindings)} results from SPARQL query")
    
    for binding in bindings:
        doc = {
            'url': binding.get('work', {}).get('value', ''),
            'cellar_id': binding.get('cellar_id', {}).get('value', ''),
            'type': binding.get('cellar_output_type', {}).get('value', ''),
            'category': binding.get('concept_name', {}).get('value', ''),
            'celex_id': binding.get('celex_id', {}).get('value', ''),
            'title': binding.get('title', {}).get('value', ''),
            'published_date': binding.get('work_date', {}).get('value', '')
        }
        documents.append(doc)
    
    return documents

def store_documents(documents):
    """Store proposals in SQLite database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    ensure_text_column(cursor)

    count = 0
    errors = 0
    
    for doc in documents:
        try:
            # Generate unique ID for primary key
            doc_id = generate_unique_id()
            text = fetch_document_text(doc)

            # Fallback if extracted text is empty, use the title
            if not text or not text.strip():
                text = doc.get("title", "")
            
            cursor.execute("""
            INSERT OR REPLACE INTO com_proposals 
            (id, url, type, category, celex_id, title, published_date, source, text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id,
                doc['url'],
                doc['type'],
                doc['category'],
                doc['celex_id'],
                doc['title'],
                parse_date_to_iso(doc['published_date']),
                'European Commission',
                text
            ))
            count += 1
        except Exception as e:
            print(f"Error storing proposal: {e}")
            errors += 1
    
    conn.commit()
    conn.close()
    
    print(f"✓ Stored {count} proposals in database")
    if errors:
        print(f"⚠ {errors} errors during storage")

def get_database_summary():
    """Print summary of stored proposals"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Total proposals
    cursor.execute("SELECT COUNT(*) FROM com_proposals")
    total = cursor.fetchone()[0]
    
    # By type
    cursor.execute("SELECT type, COUNT(*) FROM com_proposals GROUP BY type")
    by_type = cursor.fetchall()
    
    # By category
    cursor.execute("SELECT category, COUNT(*) FROM com_proposals GROUP BY category ORDER BY COUNT(*) DESC LIMIT 5")
    top_concepts = cursor.fetchall()
    
    conn.close()
    
    print("\n" + "=" * 50)
    print("Database Summary")
    print("=" * 50)
    print(f"Total proposals: {total}")
    print("\nProposals by type:")
    for doc_type, count in by_type:
        print(f"  {doc_type}: {count}")
    
    print("\nTop 5 categories:")
    for category, count in top_concepts:
        print(f"  {category}: {count}")


def main():
    """Main execution"""
    print("=" * 50)
    print("EU COM Proposals - SPARQL Ingest with Change Monitoring")
    print("=" * 50)
    
    # Read SPARQL query from file
    query_file = get_query_file_path()
    query = read_sparql_query(query_file)
    if not query:
        return
    
    # Execute SPARQL query
    results = execute_sparql_query(SPARQL_ENDPOINT, query)
    if not results:
        return
    
    # Parse results
    documents = parse_sparql_results(results)
    if not documents:
        print("No proposals to store")
        return
    
    # Store in database
    store_documents(documents)
    
    # Print summary
    get_database_summary()
    
    print("\n✓ Complete! Database: eu_regulatory_data.db")
    print("✓ EU COM Proposals data saved to unified regulatory database")

if __name__ == "__main__":
    main()
