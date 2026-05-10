import sqlite3


DB_PATH = "eu_regulatory_data.db"

AI_COLUMN = "AI_category"
REFINED_COLUMN = "refined_category"
COMBINED_COLUMN = "combined_categories"
OTHER_UNKNOWN = "Other/Unknown"

CATEGORY_ORDER = [
    "Payment services",
    "BNPL & Consumer Credit",
    "AML/CFT",
    "Operational resilience",
    "Data & AI",
]


def quote_ident(name):
    return '"' + name.replace('"', '""') + '"'


def split_categories(value):
    if value is None:
        return []

    return [
        category.strip()
        for category in str(value).split(";")
        if category.strip() and category.strip() != OTHER_UNKNOWN
    ]


def combine_categories(ai_value, refined_value):
    categories = set(split_categories(ai_value))
    categories.update(split_categories(refined_value))

    ordered = [
        category for category in CATEGORY_ORDER
        if category in categories
    ]

    extras = sorted(
        category for category in categories
        if category not in CATEGORY_ORDER
    )

    return "; ".join(ordered + extras)


def get_tables(conn):
    rows = conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    return [row[0] for row in rows]


def add_combined_column(conn, table_name):
    conn.execute(
        f"ALTER TABLE {quote_ident(table_name)} "
        f"ADD COLUMN {quote_ident(COMBINED_COLUMN)} TEXT"
    )


def process_table(conn, table_name):
    add_combined_column(conn, table_name)

    rows = conn.execute(f"""
        SELECT rowid, {quote_ident(AI_COLUMN)}, {quote_ident(REFINED_COLUMN)}
        FROM {quote_ident(table_name)}
    """).fetchall()

    updated = 0
    deleted = 0

    for rowid, ai_value, refined_value in rows:
        combined_value = combine_categories(ai_value, refined_value)

        if combined_value:
            conn.execute(f"""
                UPDATE {quote_ident(table_name)}
                SET {quote_ident(COMBINED_COLUMN)} = ?
                WHERE rowid = ?
            """, (combined_value, rowid))

            updated += 1

        else:
            conn.execute(f"""
                DELETE FROM {quote_ident(table_name)}
                WHERE rowid = ?
            """, (rowid,))

            deleted += 1

    conn.commit()
    print(f"{table_name}: updated {updated} rows, deleted {deleted} rows")


def main():
    conn = sqlite3.connect(DB_PATH)

    for table_name in get_tables(conn):
        process_table(conn, table_name)

    conn.close()


if __name__ == "__main__":
    main()