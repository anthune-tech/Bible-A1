#!/usr/bin/env python3
"""Download Terjemahan Baru (TB) Indonesian Bible and import to database."""

import json
import os
import sqlite3
import urllib.request

DB_PATH = os.path.join(os.path.dirname(__file__), "bible_strong.db")

# Map TB book numbers to OSIS codes
TB_TO_OSIS = {
    1: "Gen", 2: "Exod", 3: "Lev", 4: "Num", 5: "Deut",
    6: "Josh", 7: "Judg", 8: "Ruth",
    9: "1Sam", 10: "2Sam", 11: "1Kgs", 12: "2Kgs",
    13: "1Chr", 14: "2Chr", 15: "Ezra", 16: "Neh",
    17: "Esth", 18: "Job", 19: "Ps", 20: "Prov",
    21: "Eccl", 22: "Song", 23: "Isa", 24: "Jer",
    25: "Lam", 26: "Ezek", 27: "Dan", 28: "Hos",
    29: "Joel", 30: "Amos", 31: "Obad", 32: "Jonah",
    33: "Mic", 34: "Nah", 35: "Hab", 36: "Zeph",
    37: "Hag", 38: "Zech", 39: "Mal",
    40: "Matt", 41: "Mark", 42: "Luke", 43: "John",
    44: "Acts", 45: "Rom", 46: "1Cor", 47: "2Cor",
    48: "Gal", 49: "Eph", 50: "Phil", 51: "Col",
    52: "1Thess", 53: "2Thess", 54: "1Tim", 55: "2Tim",
    56: "Titus", 57: "Phlm", 58: "Heb", 59: "Jas",
    60: "1Pet", 61: "2Pet", 62: "1John", 63: "2John",
    64: "3John", 65: "Jude", 66: "Rev",
}

TB_JSON_URL = "https://raw.githubusercontent.com/godlytalias/Bible-Database/master/Indonesian/bible.json"
TB_SQLITE_URL = "https://github.com/godlytalias/Bible-Database/raw/master/Indonesian/holybible.db"


def import_from_json():
    """Download bible.json and import all verses."""
    print(f"Downloading TB from {TB_JSON_URL}...")
    urllib.request.urlretrieve(TB_JSON_URL, "/tmp/bible_tb.json")
    with open("/tmp/bible_tb.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strong_id (
            book_code TEXT,
            chapter INTEGER,
            verse INTEGER,
            text TEXT,
            PRIMARY KEY (book_code, chapter, verse)
        )
    """)
    conn.execute("DELETE FROM strong_id")
    count = 0
    for book_idx, book_entry in enumerate(data["Book"], 1):
        osis = TB_TO_OSIS.get(book_idx)
        if not osis:
            print(f"  Skipping book index {book_idx}")
            continue
        for ch_entry in book_entry["Chapter"]:
            for v_entry in ch_entry["Verse"]:
                vid = v_entry["Verseid"]
                ch = int(vid[3:5]) + 1
                vs = int(vid[5:]) + 1
                text = v_entry["Verse"].rstrip('"').strip()
                conn.execute(
                    "INSERT OR REPLACE INTO strong_id VALUES (?, ?, ?, ?)",
                    (osis, ch, vs, text),
                )
                count += 1
    conn.commit()
    conn.close()
    print(f"Imported {count} TB verses")


if __name__ == "__main__":
    import_from_json()
