import json
import os
import re
import sqlite3
import unicodedata2 as unicodedata

try:
    from khmer_engine import DATASET
except ImportError:
    DATASET = []

JSON_INPUT_PATH = "chuon_nath_full.json"
DB_OUTPUT_PATH = "chuon_nath_fts.db"


def clean_khmer_unicode(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    # Remove parenthetical annotations, e.g., "ក (ន.)" -> "ក"
    text = re.sub(r"\s*\(.*?\)", "", text)
    # Remove classification dots or trailing whitespace
    text = re.sub(r"[.\s]", "", text)
    # Strip invisible spaces and soft hyphens ONLY (keep \u17d2 Coeng intact)
    text = re.sub(r"[\u200b\u00a0\u00ad]", "", text)
    return text.strip()


def build_full_fts():
    if os.path.exists(JSON_INPUT_PATH):
        print(f"Loading '{JSON_INPUT_PATH}' into memory...")
        with open(JSON_INPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        print(f"'{JSON_INPUT_PATH}' not found. Falling back to DATASET mock data.")
        data = DATASET

    # Remove existing database file if present
    if os.path.exists(DB_OUTPUT_PATH):
        os.remove(DB_OUTPUT_PATH)

    conn = sqlite3.connect(DB_OUTPUT_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA synchronous = OFF;")
    cursor.execute("PRAGMA journal_mode = MEMORY;")

    # 1. Create primary dictionary table
    cursor.execute("""
        CREATE TABLE dictionary (
            id INTEGER PRIMARY KEY,
            headword TEXT NOT NULL,
            norm_headword TEXT NOT NULL,
            pos TEXT,
            definition TEXT NOT NULL
        );
    """)

    # 2. Create index on norm_headword AFTER table creation
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_dictionary_norm ON dictionary(norm_headword);"
    )

    # 3. Create FTS5 virtual table
    cursor.execute("""
        CREATE VIRTUAL TABLE dict_fts USING fts5(
            headword,
            norm_headword,
            definition,
            content='dictionary',
            content_rowid='id',
            tokenize='trigram'
        );
    """)

    print(f"Ingesting {len(data)} entries...")

    rows_dict = []
    rows_fts = []

    # Locate this section inside build_full_fts():
    for idx, item in enumerate(data, start=1):
        item_id = item.get("id", idx)
        
        # Update key lookups to handle t_main, t_pos, and t_exp
        headword = item.get("t_main") or item.get("headword") or item.get("word", "")
        pos = item.get("t_pos") or item.get("pos") or item.get("type", "")
        definition = item.get("t_exp") or item.get("definition") or item.get("meaning", "")

        norm_hw = clean_khmer_unicode(headword)
        clean_def = clean_khmer_unicode(definition)

        rows_dict.append((item_id, headword, norm_hw, pos, clean_def))
        rows_fts.append((item_id, headword, norm_hw, clean_def))

    cursor.executemany(
        "INSERT INTO dictionary (id, headword, norm_headword, pos, definition) VALUES (?, ?, ?, ?, ?)",
        rows_dict,
    )
    cursor.executemany(
        "INSERT INTO dict_fts (rowid, headword, norm_headword, definition) VALUES (?, ?, ?, ?)",
        rows_fts,
    )

    conn.commit()
    cursor.execute("PRAGMA journal_mode = WAL;")
    conn.close()

    print(f"Database populated with {len(data)} entries successfully at '{DB_OUTPUT_PATH}'!")


if __name__ == "__main__":
    build_full_fts()
