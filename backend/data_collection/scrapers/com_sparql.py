import io
import re
import sqlite3
import zipfile
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from urllib.parse import urljoin
from ...db_init import initialize_database, get_db_name, generate_unique_id, parse_date_to_iso
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

initialize_database()
DB_NAME = get_db_name()

SPARQL_ENDPOINT = "http://publications.europa.eu/webapi/rdf/sparql"
QUERY_FILE_PATH = "backend/data_collection/queries/com_queries.rq"

CELLAR_ACCEPT_HEADERS = {
    'Accept': (
        'application/xhtml+xml, text/html, text/html;type=simplified, '
        'application/zip;mtype=fmx4, application/xml;mtype=fmx4, '
        'application/xml;notice=object, text/plain'
    ),
    'Accept-Language': 'eng',
}


def html_to_text(html):
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup(['script', 'style']):
        tag.decompose()
    # Add space between inline spans to prevent word concatenation
    for tag in soup.find_all(['span', 'a']):
        tag.append(' ')
    return soup.get_text('\n', strip=True)


def xml_to_text(xml):
    """Extract text from XML content."""
    soup = BeautifulSoup(xml, 'lxml-xml')
    return soup.get_text('\n', strip=True)


# def extract_text_from_bytes(content, filename='', content_type=''):
#     """Extract text from content bytes."""
#     text = content.decode('utf-8', errors='replace')
#     if filename.lower().endswith(('.html', '.xhtml')) or 'html' in content_type.lower():
#         return html_to_text(text)
#     if filename.lower().endswith('.xml') or 'xml' in content_type.lower():
#         return xml_to_text(text)
#     return text


# def extract_zip_text(content):
#     """Extract text from all files in a ZIP."""
#     texts = []
#     with zipfile.ZipFile(io.BytesIO(content)) as archive:
#         for name in archive.namelist():
#             if name.lower().endswith(('.html', '.xhtml', '.xml')):
#                 texts.append(extract_text_from_bytes(archive.read(name), name))
#     return '\n\n'.join(text for text in texts if text).strip()


# def fetch_url_text(url):
#     """Download and extract text from a URL."""
#     response = requests.get(url, headers=CELLAR_ACCEPT_HEADERS, timeout=60)
#     response.raise_for_status()
    
#     content_type = response.headers.get('Content-Type', '').lower()
    
#     if 'zip' in content_type or response.content.startswith(b'PK'):
#         return extract_zip_text(response.content)
    
#     return extract_text_from_bytes(response.content, url, content_type)

def clean_text(text):
    lines = text.split('\n')
    # Drop first line if it looks like a filename
    if lines and any(x in lines[0] for x in ['%28', 'xhtml', '_EN_', '.docx']):
        lines = lines[1:]
    text = '\n'.join(line.strip() for line in lines if line.strip()) # Remove empty lines and trim whitespace
    text = re.sub(r'\(\d+\)', '', text) # Remove footnote markers like (1), (2), etc.
    text = re.sub(r'([a-z])\.([A-Z])', r'\1. \2', text) # Add space after periods if missing 
    text = re.sub(r'([A-Z]{2,})\s+([A-Z][a-z])', r'\1\n\2', text) # Split lines between all-caps and normal text (e.g. "REGULATION 2020/1234" -> "REGULATION\n2020/1234")
    return text.rstrip()

def fetch_document_text(doc):
    cellar_id = doc['cellar_id'].strip()
    url = f'http://publications.europa.eu/resource/cellar/{cellar_id}'
    response = requests.get(url, headers=CELLAR_ACCEPT_HEADERS, timeout=60)
    if '300 Multiple-Choice' in response.text:
        url = re.search(r'href="(http[^"]+)"', response.text).group(1)
        response = requests.get(url, headers=CELLAR_ACCEPT_HEADERS, timeout=60)
    return html_to_text(response.content.decode('utf-8', errors='replace'))


def read_sparql_query(filename):
    """Read SPARQL query from file."""
    with open(filename, 'r', encoding='utf-8') as f:
        return f.read()


def execute_sparql_query(endpoint, query):
    """Execute SPARQL query and return results."""
    print(f"Executing SPARQL query against {endpoint}...")
    
    response = requests.post(
        endpoint,
        headers={
            'Accept': 'application/sparql-results+json',
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        data={'query': query},
        timeout=60
    )
    response.raise_for_status()
    return response.json()


def parse_sparql_results(results):
    """Parse SPARQL JSON results into list of proposals."""
    bindings = results['results']['bindings']
    print(f"Found {len(bindings)} results from SPARQL query")
    
    documents = []
    for binding in bindings:
        doc = {
            'url': binding['work']['value'],
            'cellar_id': binding['cellar_id']['value'],
            'type': binding['cellar_output_type']['value'],
            'category': binding['concept_name']['value'],
            'celex_id': binding.get('celex_id', {}).get('value', ''),
            'title': binding['title']['value'],
            'published_date': binding['work_date']['value']
        }
        documents.append(doc)
    
    return documents


def store_documents(documents):
    """Store proposals in SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for doc in documents:
        doc_id = generate_unique_id()
        text = clean_text(fetch_document_text(doc))
        
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
    
    conn.commit()
    conn.close()
    print(f"✓ Stored {len(documents)} proposals in database")


def main():
    """Main execution."""
    query = read_sparql_query(QUERY_FILE_PATH)
    results = execute_sparql_query(SPARQL_ENDPOINT, query)
    documents = parse_sparql_results(results)
    store_documents(documents)
    print("\n✓ Complete! Database: eu_regulatory_data.db")


if __name__ == "__main__":
    main()
