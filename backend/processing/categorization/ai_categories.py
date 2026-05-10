import json
import sqlite3
import requests

DB_PATH = "eu_regulatory_data.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"

ALLOWED_CATEGORIES = [
    "Payment services",
    "BNPL & Consumer Credit",
    "AML/CFT",
    "Operational resilience",
    "Data & AI",
    "Other/Unknown",
]

def classify_text(text):
    if not text:
        return ["Other/Unknown"]

    prompt = f"""
You are classifying EU regulatory database rows.

The project is related to buy now pay later and relevant EU regulatory documents.
Classify the document into one or more allowed categories.

Allowed categories:
{json.dumps(ALLOWED_CATEGORIES, indent=2)}

Guidance:
Classify the regulatory document into one or more of these categories for a buy now pay later regulatory database:

1. Payment services: PSD2, PSD3, PSR, payment services, electronic money, settlement
2. BNPL & Consumer Credit: BNPL, buy now pay later, CCD2, consumer credit, lending
3. AML/CFT: AML, CFT, AMLD6, money laundering, TFR, travel rule
4. Operational resilience: DORA, ICT risk, cyber resilience, cybersecurity
5. Data & AI: GDPR, AI Act, artificial intelligence, data protection, personal data

Use your knowledge even if you don't see exact keywords.
Use Other/Unknown only if none of the main categories fit.

Document text:
{str(text).strip()[:8000]}

Return only this JSON shape:
{{"categories": ["one or more allowed categories"]}}
"""

    response = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0, "num_ctx": 8192},
    }, timeout=120)
    response.raise_for_status()

    categories = json.loads(response.json()["response"]).get("categories", [])
    cleaned = [c for c in categories if c in ALLOWED_CATEGORIES]
    return [c for c in cleaned if c != "Other/Unknown"] or ["Other/Unknown"]


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for (table,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        cur.execute(f'ALTER TABLE "{table}" ADD COLUMN ai_category TEXT')
        rows = cur.execute(f'SELECT rowid, text FROM "{table}"').fetchall()
        print(f"\nProcessing {table}: {len(rows)} rows")

        for i, (rowid, text) in enumerate(rows, 1):
            value = "; ".join(classify_text(text))
            cur.execute(f'UPDATE "{table}" SET ai_category = ? WHERE rowid = ?', (value, rowid))
            if i % 10 == 0:
                conn.commit()
                print(f"  {i}/{len(rows)}")

        conn.commit()

    conn.close()


if __name__ == "__main__":
    main()