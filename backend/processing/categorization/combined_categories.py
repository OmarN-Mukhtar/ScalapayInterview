import sqlite3

DB_PATH = "eu_regulatory_data.db"
CATEGORY_ORDER = ["Payment services", "BNPL & Consumer Credit", "AML/CFT", "Operational resilience", "Data & AI"]

def combine_categories(ai, refined):
    cats = set()
    for val in [ai, refined]:
        if val:
            cats.update(c.strip() for c in val.split(";") if c.strip() and c.strip() != "Other/Unknown")
    ordered = [c for c in CATEGORY_ORDER if c in cats]
    extras = sorted(c for c in cats if c not in CATEGORY_ORDER)
    return "; ".join(ordered + extras)

def main():
    conn = sqlite3.connect(DB_PATH)
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN combined_categories TEXT')
        rows = conn.execute(f'SELECT rowid, AI_category, refined_category FROM "{table}"').fetchall()
        for rowid, ai, refined in rows:
            combined = combine_categories(ai, refined)
            if combined:
                conn.execute(f'UPDATE "{table}" SET combined_categories = ? WHERE rowid = ?', (combined, rowid))
            else:
                conn.execute(f'DELETE FROM "{table}" WHERE rowid = ?', (rowid,))
        conn.commit()
    conn.close()

if __name__ == "__main__":
    main()