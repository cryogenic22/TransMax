"""
Database migration: Add Black Book v2 columns to translation_rules table.
Safe to run multiple times (checks if columns exist before adding).
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "transmax.db")

NEW_COLUMNS = [
    ("source_language", "TEXT"),
    ("target_language", "TEXT"),
    ("project_id", "TEXT"),
    ("domain", "TEXT DEFAULT 'general'"),
    ("is_regex", "BOOLEAN DEFAULT 0"),
    ("is_strict", "BOOLEAN DEFAULT 0"),
    ("priority", "INTEGER DEFAULT 0"),
    ("description", "TEXT"),
    ("fire_count", "INTEGER DEFAULT 0"),
    ("last_fired_at", "DATETIME"),
    ("false_positive_count", "INTEGER DEFAULT 0"),
    ("created_by", "TEXT"),
]


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}, skipping migration.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='translation_rules'")
    if not cursor.fetchone():
        print("translation_rules table not found. It will be created on app startup.")
        conn.close()
        return

    # Get existing columns
    cursor.execute("PRAGMA table_info(translation_rules)")
    existing = {row[1] for row in cursor.fetchall()}

    added = 0
    for col_name, col_type in NEW_COLUMNS:
        if col_name not in existing:
            sql = f"ALTER TABLE translation_rules ADD COLUMN {col_name} {col_type}"
            cursor.execute(sql)
            print(f"  Added column: {col_name}")
            added += 1

    conn.commit()
    conn.close()
    print(f"Migration complete. Added {added} columns.")


if __name__ == "__main__":
    migrate()
