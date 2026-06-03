#!/usr/bin/env python3
"""Download Matthew Henry's Complete Commentary from OpenChristianData and import to database."""

import json
import os
import sqlite3
import urllib.request

DB_PATH = os.path.join(os.path.dirname(__file__), "bible_strong.db")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "commentary")

BASE_URL = "https://raw.githubusercontent.com/OpenChristianData/open-christian-data/main/data/commentaries/matthew-henry"

OSIS_TO_SLUG = {
    "Gen": "genesis", "Exod": "exodus", "Lev": "leviticus", "Num": "numbers", "Deut": "deuteronomy",
    "Josh": "joshua", "Judg": "judges", "Ruth": "ruth",
    "1Sam": "1-samuel", "2Sam": "2-samuel", "1Kgs": "1-kings", "2Kgs": "2-kings",
    "1Chr": "1-chronicles", "2Chr": "2-chronicles", "Ezra": "ezra", "Neh": "nehemiah",
    "Esth": "esther", "Job": "job", "Ps": "psalms", "Prov": "proverbs",
    "Eccl": "ecclesiastes", "Song": "song-of-solomon", "Isa": "isaiah", "Jer": "jeremiah",
    "Lam": "lamentations", "Ezek": "ezekiel", "Dan": "daniel",
    "Hos": "hosea", "Joel": "joel", "Amos": "amos", "Obad": "obadiah",
    "Jonah": "jonah", "Mic": "micah", "Nah": "nahum", "Hab": "habakkuk",
    "Zeph": "zephaniah", "Hag": "haggai", "Zech": "zechariah", "Mal": "malachi",
    "Matt": "matthew", "Mark": "mark", "Luke": "luke", "John": "john",
    "Acts": "acts", "Rom": "romans", "1Cor": "1-corinthians", "2Cor": "2-corinthians",
    "Gal": "galatians", "Eph": "ephesians", "Phil": "philippians", "Col": "colossians",
    "1Thess": "1-thessalonians", "2Thess": "2-thessalonians", "1Tim": "1-timothy", "2Tim": "2-timothy",
    "Titus": "titus", "Phlm": "philemon", "Heb": "hebrews",
    "Jas": "james", "1Pet": "1-peter", "2Pet": "2-peter",
    "1John": "1-john", "2John": "2-john", "3John": "3-john", "Jude": "jude", "Rev": "revelation",
}


def download_json(url, cache_path):
    if os.path.exists(cache_path):
        print(f"  Using cached {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    print(f"  Downloading {url}...")
    urllib.request.urlretrieve(url, cache_path)
    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_verse_range(vr):
    if not vr or vr == "intro" or vr == "title":
        return None, None
    parts = vr.split("-")
    try:
        start = int(parts[0])
        end = int(parts[1]) if len(parts) > 1 else start
        return start, end
    except ValueError:
        return None, None


def import_commentary():
    os.makedirs(CACHE_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bible_commentary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_code TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse_range TEXT,
            verse_start INTEGER,
            verse_end INTEGER,
            source TEXT NOT NULL DEFAULT 'matthew-henry',
            commentary_text TEXT NOT NULL,
            word_count INTEGER,
            entry_id TEXT UNIQUE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comm_lookup ON bible_commentary(book_code, chapter, verse_start, verse_end)")

    conn.execute("DELETE FROM bible_commentary WHERE source = 'matthew-henry'")

    total = 0
    for osis_code, slug in sorted(OSIS_TO_SLUG.items()):
        url = f"{BASE_URL}/{slug}.json"
        cache_path = os.path.join(CACHE_DIR, f"{slug}.json")
        try:
            data = download_json(url, cache_path)
        except Exception as e:
            print(f"  SKIP {osis_code} ({slug}): {e}")
            continue

        entries = data.get("data", [])
        book_count = 0
        for entry in entries:
            entry_id = entry.get("entry_id")
            chapter = entry.get("chapter", 0)
            verse_range = entry.get("verse_range", "intro")
            text = entry.get("commentary_text", "").strip()
            wc = entry.get("word_count", 0)
            vs, ve = parse_verse_range(verse_range)

            conn.execute(
                "INSERT OR IGNORE INTO bible_commentary "
                "(book_code, chapter, verse_range, verse_start, verse_end, source, commentary_text, word_count, entry_id) "
                "VALUES (?, ?, ?, ?, ?, 'matthew-henry', ?, ?, ?)",
                (osis_code, chapter, verse_range, vs, ve, text, wc, entry_id),
            )
            book_count += 1

        conn.commit()
        total += book_count
        print(f"  {osis_code}: {book_count} entries")

    conn.close()
    print(f"\nImported {total} total entries")


if __name__ == "__main__":
    import_commentary()
