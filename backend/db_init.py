import sqlite3
import uuid
from datetime import datetime
from dateutil import parser as date_parser

# Shared database name
DB_NAME = "eu_regulatory_data.db"

def initialize_database():
    """Initialize unified database schema for consultations and COM documents"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create COM consultations table (RSS Feed data)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS com_consultations (
        id TEXT PRIMARY KEY,
        url TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        published_date TEXT,
        type TEXT DEFAULT 'Public Consultation',
        category TEXT,
        status TEXT,
        opening_date TEXT,
        deadline_date TEXT,
        text TEXT,
        summary TEXT,
        source TEXT DEFAULT 'European Commission',
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create COM proposals table (SPARQL data)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS com_proposals (
        id TEXT PRIMARY KEY,
        url TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL,
        category TEXT,
        celex_id TEXT UNIQUE,
        title TEXT NOT NULL,
        published_date TEXT,
        text TEXT,
        summary TEXT,
        status TEXT DEFAULT 'Proposal',
        source TEXT DEFAULT 'European Commission',
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    

    # EBA Guidelines table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eba_guidelines (
        id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        published_date TEXT,
        document_url TEXT UNIQUE,
        url TEXT,
        type TEXT DEFAULT 'Guidelines',
        source TEXT DEFAULT 'EBA',
        text TEXT,
        summary TEXT,
        status TEXT DEFAULT 'Final',
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # EBA RTS (Regulatory Technical Standards) table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eba_rts (
        id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        published_date TEXT,
        document_url TEXT UNIQUE,
        url TEXT,
        type TEXT DEFAULT 'RTS',
        source TEXT DEFAULT 'EBA',
        text TEXT,
        summary TEXT,
        status TEXT DEFAULT 'Draft',
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    

    # Indexes for COM consultations
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_consult_title ON com_consultations(title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_consult_published ON com_consultations(published_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_consult_type ON com_consultations(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_consult_category ON com_consultations(category)")
    
    # Indexes for COM proposals
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_type ON com_proposals(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_celex ON com_proposals(celex_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_category ON com_proposals(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_title ON com_proposals(title)")
    
    # Indexes for EBA Guidelines
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eba_guide_category ON eba_guidelines(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eba_guide_title ON eba_guidelines(title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eba_guide_date ON eba_guidelines(published_date)")
    
    # Indexes for EBA RTS
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eba_rts_category ON eba_rts(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eba_rts_title ON eba_rts(title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eba_rts_date ON eba_rts(published_date)")
    
    conn.commit()
    conn.close()
    print(f"✓ Unified database initialized: {DB_NAME}")

def get_db_name():
    """Return database name"""
    return DB_NAME

def generate_unique_id():
    """Generate a unique UUID for database entries"""
    return str(uuid.uuid4())

def generate_id_from_link(link):
    """Generate a deterministic unique ID from a link (for consistency)"""
    import hashlib
    return hashlib.sha256(link.encode()).hexdigest()[:16]

def parse_date_to_iso(date_string):
    """Parse various date formats and return ISO format (YYYY-MM-DD)"""
    if not date_string:
        return None
    
    try:
        # Try parsing with dateutil (handles ISO, RFC 2822, and many other formats)
        parsed_date = date_parser.parse(date_string)
        return parsed_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return None

if __name__ == "__main__":
    initialize_database()
