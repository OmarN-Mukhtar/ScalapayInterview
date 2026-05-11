import sqlite3
from datetime import date, datetime

DB_PATH = "eu_regulatory_data.db"
TABLE_NAME = "eba_rts"

UNKNOWN_VALUES = {"other", "unknown", "other/unknown", "", None}


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        return None


def is_unknown(value):
    if value is None:
        return True
    return value.strip().lower() in UNKNOWN_VALUES


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Add columns 
for column in [
    "relevance INTEGER",
    "urgency INTEGER",
    "data_confidence INTEGER",
    "score REAL",
    "urgency_level TEXT",
]:
    try:
        cur.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {column}")
    except sqlite3.OperationalError:
        pass

rows = cur.execute(f"""
    SELECT id, status, keyword_count, deadline_date, refined_category, ai_category
    FROM {TABLE_NAME}
""").fetchall()

# Group keyword counts by status
status_groups = {}

for row in rows:
    status = row["status"] or "Unknown"
    keyword_count = row["keyword_count"] or 0
    status_groups.setdefault(status, []).append(keyword_count)

# Calculate 25th and 75th percentile cutoffs per status
percentiles = {}

for status, counts in status_groups.items():
    counts = sorted(counts)

    p25_index = int(len(counts) * 0.25)
    p75_index = int(len(counts) * 0.75)

    percentiles[status] = {
        "p25": counts[p25_index],
        "p75": counts[p75_index],
    }

today = date.today()

for row in rows:
    status = row["status"] or "Unknown"
    keyword_count = row["keyword_count"] or 0

    p25 = percentiles[status]["p25"]
    p75 = percentiles[status]["p75"]

    # 1. Relevance score
    if keyword_count >= p75:
        relevance = 100
    elif keyword_count >= p25:
        relevance = 50
    else:
        relevance = 25

    # 2. Urgency score based on deadline_date age
    deadline = parse_date(row["deadline_date"])

    if deadline is None:
        urgency = 5
    else:
        age_years = (today - deadline).days / 365.25

        if age_years > 10:
            urgency = 5
        elif age_years > 6:
            urgency = 30
        elif age_years > 4:
            urgency = 50
        elif age_years > 2:
            urgency = 75
        else:
            urgency = 100

    # 3. Data confidence score
    refined_unknown = is_unknown(row["refined_category"])
    ai_unknown = is_unknown(row["ai_category"])

    if refined_unknown and not ai_unknown:
        data_confidence = 20
    elif not refined_unknown and ai_unknown:
        data_confidence = 50
    elif not refined_unknown and not ai_unknown:
        data_confidence = 100
    else:
        data_confidence = 20

    # Final weighted score
    score = (
        relevance * 0.40
        + urgency * 0.40
        + data_confidence * 0.20
    )

    # Urgency level
    if score > 75:
        urgency_level = "high"
    elif score >= 40:
        urgency_level = "medium"
    else:
        urgency_level = "low"

    cur.execute(f"""
        UPDATE {TABLE_NAME}
        SET relevance = ?,
            urgency = ?,
            data_confidence = ?,
            score = ?,
            urgency_level = ?
        WHERE id = ?
    """, (
        relevance,
        urgency,
        data_confidence,
        round(score, 2),
        urgency_level,
        row["id"],
    ))

conn.commit()
conn.close()

print(f"{TABLE_NAME} scores added successfully.")
