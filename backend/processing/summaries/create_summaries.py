import sqlite3
import json
import urllib.request
import urllib.error
from pathlib import Path

DB_PATH = "eu_regulatory_data.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:4b"

TABLES = [
    "com_consultations",
    "com_proposals",
    "eba_guidelines",
    "eba_rts",
]

MAX_CHARS = 12000


def ask_ollama(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "").strip()



def make_prompt(title: str, text: str) -> str:
    source_text = text.strip() if text and text.strip() else title.strip()

    if len(source_text) > MAX_CHARS:
        source_text = source_text[:MAX_CHARS] + "\n\n[Text truncated]"

    return f"""
Create a concise one-paragraph summary of the following regulatory text.

Rules:
- Write only one paragraph.
- Do not add information that is not present in the text.
- If the text is only a title, summarize it as a placeholder based on the title.

Title:
{title}

Text:
{source_text}
""".strip()


def summarize_database(db_path: str):
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    for table in TABLES:
        print(f"\nProcessing table: {table}")

        rows = cur.execute(
            f"""
            SELECT id, title, text
            FROM {table}
            WHERE summary IS NULL OR TRIM(summary) = ''
            """
        ).fetchall()

        print(f"Rows needing summaries: {len(rows)}")

        for i, row in enumerate(rows, start=1):
            row_id = row["id"]
            title = row["title"] or ""
            text = row["text"] or ""

            print(f"[{i}/{len(rows)}] Summarizing: {title[:80]}")

            if not text.strip() and not title.strip():
                print("  Skipped: no text or title")
                continue

            prompt = make_prompt(title, text)
            summary = ask_ollama(prompt)

            cur.execute(
                f"""
                UPDATE {table}
                SET summary = ?
                WHERE id = ?
                """,
                (summary, row_id),
            )

            conn.commit()

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    summarize_database(DB_PATH)
