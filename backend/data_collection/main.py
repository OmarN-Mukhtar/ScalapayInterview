"""
Data Collection Orchestrator
Aggregates data from multiple EU regulatory sources
"""

import sys
import time
from datetime import datetime

from backend.db_init import initialize_database, get_db_name
from backend.data_collection.scrapers.com_consultations import main as com_consultation_main
from backend.data_collection.scrapers.com_sparql import main as com_sparql_main
from backend.data_collection.scrapers.eba_guidelines import scrape_all as eba_guidelines_scrape
from backend.data_collection.scrapers.eba_rts import scrape_all as eba_rts_scrape


def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def main():
    """Main orchestration function"""
    start_time = datetime.now()
    
    print_header("EU REGULATORY DATA COLLECTION SYSTEM")
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize database
    print_header("STEP 1: DATABASE INITIALIZATION")
    initialize_database()
    db_name = get_db_name()
    
    # Run COM Consultations (RSS Feed)
    print_header("STEP 2: EU FINANCE CONSULTATIONS (RSS Feed)")
    try:
        com_consultation_main()
    except Exception as e:
        print(f"⚠ Error in COM Consultations: {e}")
    
    time.sleep(1)
    
    # Run COM Documents (SPARQL)
    print_header("STEP 3: COM DOCUMENTS (SPARQL)")
    try:
        com_sparql_main()
    except Exception as e:
        print(f"⚠ Error in COM SPARQL: {e}")
    
    time.sleep(1)
    
    # Run EBA Guidelines
    print_header("STEP 4: EBA GUIDELINES")
    try:
        inserted, skipped = eba_guidelines_scrape()
        print(f"✓ Inserted {inserted} new EBA Guidelines")
        print(f"✓ Skipped {skipped} duplicate entries")
    except Exception as e:
        print(f"⚠ Error in EBA Guidelines: {e}")
    
    time.sleep(1)
    
    # Run EBA RTS
    print_header("STEP 5: EBA RTS (REGULATORY TECHNICAL STANDARDS)")
    try:
        inserted, skipped = eba_rts_scrape()
        print(f"✓ Inserted {inserted} new EBA RTS")
        print(f"✓ Skipped {skipped} duplicate entries")
    except Exception as e:
        print(f"⚠ Error in EBA RTS: {e}")
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print_header("DATA COLLECTION COMPLETE")
    print(f"Database: {db_name}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
