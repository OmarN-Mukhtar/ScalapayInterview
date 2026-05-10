import json
import sqlite3
import requests

DB_PATH = "eu_regulatory_data.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"


def summarize_text(title, text):
    source = text.strip() if text and text.strip() else title.strip()
    prompt = f"""
Create a concise one-paragraph summary of the following regulatory text. Make the summary relevant to a buy now pay later service in Europe.
Focus on relevance to their compliance and regulatory obligations, not on general descriptions. 
Rules:
- Write only one paragraph.
- Do not add information that is not present in the text.
- If the text is only a title, summarize it as a placeholder based on the title.

Title:
{title}

Text:
{source[:12000]}
""".strip()

    response = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }, timeout=180)
    response.raise_for_status()
    return response.json().get("response", "").strip()


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for (table,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        rows = cur.execute(f'SELECT id, title, text FROM "{table}" WHERE summary IS NULL OR TRIM(summary) = ""').fetchall()
        print(f"\nProcessing {table}: {len(rows)} rows")

        for i, (row_id, title, text) in enumerate(rows, 1):
            if not (title or text):
                continue
            cur.execute(f'UPDATE "{table}" SET summary = ? WHERE id = ?', (summarize_text(title or "", text or ""), row_id))
            if i % 10 == 0:
                conn.commit()
                print(f"  {i}/{len(rows)}")

        conn.commit()

    conn.close()


if __name__ == "__main__":
    main()