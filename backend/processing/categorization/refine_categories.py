import re
import sqlite3

DB_PATH = "eu_regulatory_data.db"


CATEGORY_ORDER = [
    "Payment services",
    "BNPL & Consumer Credit",
    "AML/CFT",
    "Operational resilience",
    "Data & AI",
    "Other/Unknown",
]

WEAK_PRIOR_MAP = {
    "Payment services and electronic money": ["Payment services"],
    "electronic money": ["Payment services"],
    "payment": ["Payment services"],
    "intra-EU payment": ["Payment services"],
    "financial transaction": ["Payment services"],
    "Consumer protection": ["BNPL & Consumer Credit"],
    "credit": ["BNPL & Consumer Credit"],
    "loan": ["BNPL & Consumer Credit"],
    "AML and CFT": ["AML/CFT"],
    "money laundering": ["AML/CFT"],
    "operational_resilience": ["Operational resilience"],
    "European Union Agency for Cybersecurity": ["Operational resilience"],
    "computer crime": ["Operational resilience"],
    "computer system": ["Operational resilience"],
    "data_ai": ["Data & AI"],
    "data protection": ["Data & AI"],
    "personal data": ["Data & AI"],
}

KEYWORDS = {
    "Payment services": [
        "PSD2", "PSD3", "PSR", "Payment Services Directive",
        "Payment Services Regulation", "payment service", "payment services",
        "settlement", "authorisation", "authorization",
    ],
    "BNPL & Consumer Credit": [
        "BNPL", "buy now pay later", "Consumer Credit Directive", "CCD2",
        "consumer credit", "responsible lending", "credit agreement",
        "credit agreements", "lending obligation", "lending obligations",
    ],
    "AML/CFT": [
        "AML", "CFT", "AMLD6", "anti-money laundering",
        "countering the financing of terrorism", "counter-terrorist financing",
        "terrorist financing", "Transfer of Funds Regulation", "TFR",
        "Travel Rule", "EBA AML", "money laundering",
    ],
    "Operational resilience": [
        "DORA", "Digital Operational Resilience Act", "operational resilience",
        "ICT risk", "ICT third-party", "cyber resilience", "cybersecurity",
        "incident reporting",
    ],
    "Data & AI": [
        "GDPR", "General Data Protection Regulation", "EU AI Act", "AI Act",
        "artificial intelligence", "data protection", "personal data",
        "credit decisioning", "fraud model", "fraud models",
        "automated decision", "automated decision-making",
    ],
}


def get_tables(conn):
    rows = conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    return [row[0] for row in rows]


def add_output_columns(conn, table_name):
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN refined_category TEXT")
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN keyword_count INTEGER")


def keyword_matches(text):
    categories = set()
    keywords = set()

    for category, terms in KEYWORDS.items():
        for term in terms:
            pattern = r"\b" + re.escape(term) + r"\b"

            if re.search(pattern, text, flags=re.IGNORECASE):
                categories.add(category)
                keywords.add(term.lower())

    return categories, keywords


def refine_row(category, text):
    refined = set(WEAK_PRIOR_MAP.get(category.strip(), []))

    matched_categories, matched_keywords = keyword_matches(text or "")
    refined.update(matched_categories)

    if not refined:
        refined.add("Other/Unknown")

    refined_value = "; ".join(
        category for category in CATEGORY_ORDER
        if category in refined
    )

    return refined_value, len(matched_keywords)


def process_table(conn, table_name):
    add_output_columns(conn, table_name)

    rows = conn.execute(f"""
        SELECT rowid, category, text
        FROM {table_name}
    """).fetchall()

    updated = 0

    for rowid, category, text in rows:
        refined_category, keyword_count = refine_row(category or "", text or "")

        conn.execute(f"""
            UPDATE {table_name}
            SET refined_category = ?,
                keyword_count = ?
            WHERE rowid = ?
        """, (refined_category, keyword_count, rowid))

        updated += 1

    conn.commit()
    print(f"{table_name}: updated {updated} rows")


def main():
    conn = sqlite3.connect(DB_PATH)

    for table_name in get_tables(conn):
        process_table(conn, table_name)

    conn.close()


if __name__ == "__main__":
    main()