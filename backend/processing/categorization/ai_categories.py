import json
import time
import sqlite3
from pathlib import Path

import requests


DB_PATH = "eu_regulatory_data.db"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"

AI_COLUMN = "AI_category"

ALLOWED_CATEGORIES = [
    "Payment services",
    "BNPL & Consumer Credit",
    "AML/CFT",
    "Operational resilience",
    "Data & AI",
    "Other/Unknown",
]

CATEGORY_GUIDANCE = """
Classify the regulatory document into one or more of these categories:

1. Payment services: PSD2, PSD3, PSR, payment services, electronic money, settlement
2. BNPL & Consumer Credit: BNPL, buy now pay later, CCD2, consumer credit, lending
3. AML/CFT: AML, CFT, AMLD6, money laundering, TFR, travel rule
4. Operational resilience: DORA, ICT risk, cyber resilience, cybersecurity
5. Data & AI: GDPR, AI Act, artificial intelligence, data protection, personal data

Use Other/Unknown only if none of the main categories fit.
"""


def quote_ident(name):
    return '"' + name.replace('"', '""') + '"'


def clean_text(text, max_chars=8000):
    text = "" if text is None else str(text).strip()

    if len(text) > max_chars:
        return text[:max_chars] + "\n[TRUNCATED]"

    return text


def get_tables(conn):
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    return [row[0] for row in rows]


def add_ai_column(conn, table_name):
    cur = conn.cursor()

    columns = cur.execute(
        f"PRAGMA table_info({quote_ident(table_name)})"
    ).fetchall()

    existing_columns = {col[1] for col in columns}

    if AI_COLUMN not in existing_columns:
        cur.execute(
            f"ALTER TABLE {quote_ident(table_name)} "
            f"ADD COLUMN {quote_ident(AI_COLUMN)} TEXT"
        )
        conn.commit()


def call_ollama(prompt):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "num_ctx": 8192,
        },
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()

    return json.loads(response.json()["response"])


def clean_categories(categories):
    if not isinstance(categories, list):
        return ["Other/Unknown"]

    cleaned = []

    for category in categories:
        category = str(category).strip()

        if category in ALLOWED_CATEGORIES and category not in cleaned:
            cleaned.append(category)

    main_categories = [
        category for category in cleaned
        if category != "Other/Unknown"
    ]

    return main_categories or ["Other/Unknown"]


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
{CATEGORY_GUIDANCE}

Document text:
{text}

Return only this JSON shape:
{{"categories": ["one or more allowed categories"]}}
"""

    result = call_ollama(prompt)
    return clean_categories(result.get("categories"))


def refine_table(conn, table_name):
    cur = conn.cursor()

    add_ai_column(conn, table_name)

    rows = cur.execute(f"""
        SELECT rowid, text
        FROM {quote_ident(table_name)}
    """).fetchall()

    print(f"\nProcessing {table_name}: {len(rows)} rows")

    for index, (rowid, text) in enumerate(rows, start=1):
        categories = classify_text(clean_text(text))
        value = "; ".join(categories)

        cur.execute(f"""
            UPDATE {quote_ident(table_name)}
            SET {quote_ident(AI_COLUMN)} = ?
            WHERE rowid = ?
        """, (value, rowid))

        if index % 10 == 0:
            conn.commit()
            print(f"  {index}/{len(rows)} rows processed")

    conn.commit()
    print(f"{table_name}: updated {len(rows)} rows")


def main():
    db_path = Path(DB_PATH)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)

    for table_name in get_tables(conn):
        refine_table(conn, table_name)

    conn.close()


if __name__ == "__main__":
    main()