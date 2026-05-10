import re
import sqlite3

DB_PATH = "eu_regulatory_data.db"

CATEGORY_ORDER = ["Payment services", "BNPL & Consumer Credit", "AML/CFT", "Operational resilience", "Data & AI", "Other/Unknown"]

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
    "Payment services": ["PSD2", "PSD3", "PSR", "Payment Services Directive", "Payment Services Regulation", "payment service", "payment services", "settlement", "authorisation", "authorization"],
    "BNPL & Consumer Credit": ["BNPL", "buy now pay later", "Consumer Credit Directive", "CCD2", "consumer credit", "responsible lending", "credit agreement", "credit agreements", "lending obligation", "lending obligations"],
    "AML/CFT": ["AML", "CFT", "AMLD6", "anti-money laundering", "countering the financing of terrorism", "counter-terrorist financing", "terrorist financing", "Transfer of Funds Regulation", "TFR", "Travel Rule", "EBA AML", "money laundering"],
    "Operational resilience": ["DORA", "Digital Operational Resilience Act", "operational resilience", "ICT risk", "ICT third-party", "cyber resilience", "cybersecurity", "incident reporting"],
    "Data & AI": ["GDPR", "General Data Protection Regulation", "EU AI Act", "AI Act", "artificial intelligence", "data protection", "personal data", "credit decisioning", "fraud model", "fraud models", "automated decision", "automated decision-making"],
}


def refine_row(category, text):
    refined = set(WEAK_PRIOR_MAP.get(category.strip(), []))
    matched_keywords = set()

    for cat, terms in KEYWORDS.items():
        for term in terms:
            if re.search(r"\b" + re.escape(term) + r"\b", text, flags=re.IGNORECASE):
                refined.add(cat)
                matched_keywords.add(term.lower())

    if not refined:
        refined.add("Other/Unknown")

    return "; ".join(c for c in CATEGORY_ORDER if c in refined), len(matched_keywords)


def main():
    conn = sqlite3.connect(DB_PATH)

    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN refined_category TEXT')
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN keyword_count INTEGER')

        rows = conn.execute(f'SELECT rowid, category, text FROM "{table}"').fetchall()
        for rowid, category, text in rows:
            refined, count = refine_row(category or "", text or "")
            conn.execute(f'UPDATE "{table}" SET refined_category = ?, keyword_count = ? WHERE rowid = ?', (refined, count, rowid))

        conn.commit()

    conn.close()


if __name__ == "__main__":
    main()