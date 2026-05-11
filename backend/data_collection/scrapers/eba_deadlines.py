import sqlite3
import requests

from ...db_init import initialize_database, get_db_name, parse_date_to_iso

DB_PATH = "eu_regulatory_data.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"


def extract_deadline(title, text):
    """Extract deadline date from text using Ollama."""
    source = text.strip() if text and text.strip() else title.strip()
    prompt = f"""
Extract the deadline date from the following regulatory text. If there is a deadline mentioned, return ONLY the date in the format YYYY-MM-DD. If no deadline exists, return "None".
Rules:
- Return only the date or "None", nothing else.
- Common deadline keywords: "deadline", "by", "until", "before", "on", "implementation date"
- If multiple deadlines exist, return the earliest one.
- Only extract dates that are clearly stated deadlines, not publication or decision dates.

Title:
{title}

Text:
{source[:8000]}
""".strip()

    response = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }, timeout=180)
    response.raise_for_status()
    result = response.json().get("response", "").strip()
    
    if result.lower() == "none" or not result:
        return None
    
    # Parse the returned date
    parsed_date = parse_date_to_iso(result)
    return parsed_date


def main():
    """Extract deadlines from eba_guidelines and eba_rts tables and update database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Initialize deadline_date column if it doesn't exist
    for table in ['eba_guidelines', 'eba_rts']:
        try:
            cur.execute(f'PRAGMA table_info("{table}")')
            columns = [col[1] for col in cur.fetchall()]
            
            if 'deadline_date' not in columns:
                print(f"Adding deadline_date column to {table}...")
                cur.execute(f'ALTER TABLE "{table}" ADD COLUMN deadline_date TEXT')
                conn.commit()
        except Exception as e:
            print(f"Warning: Could not check/add deadline_date column for {table}: {e}")
    
    # Process each table
    for table in ['eba_guidelines', 'eba_rts']:
        rows = cur.execute(f'SELECT id, text, title, published_date FROM "{table}" WHERE (deadline_date IS NULL OR TRIM(deadline_date) = "")').fetchall()
        print(f"\nProcessing {table}: {len(rows)} rows")
        
        for i, (row_id, text, title, published_date) in enumerate(rows, 1):
            if not (title or text):
                continue
            
            deadline = extract_deadline(title or "", text or "")
            
            # Only update if deadline is valid and >= published_date
            if deadline:
                if published_date and deadline < published_date:
                    print(f"  Skipping invalid deadline {deadline} (before published_date {published_date})")
                    continue
                cur.execute(f'UPDATE "{table}" SET deadline_date = ? WHERE id = ?', (deadline, row_id))
            
            if i % 10 == 0:
                conn.commit()
                print(f"  {i}/{len(rows)}")
        
        conn.commit()
    
    conn.close()
    print("\n✓ Deadline extraction complete")


if __name__ == "__main__":
    main()