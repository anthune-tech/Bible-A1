#!/usr/bin/env python3
"""Download NLT (New Living Translation) from Midvash API and import to database."""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

DB_PATH = os.path.join(os.path.dirname(__file__), "bible_strong.db")

MIDVASH_SLUG = {
    "Gen": "genesis", "Exod": "exodus", "Lev": "leviticus", "Num": "numbers",
    "Deut": "deuteronomy", "Josh": "joshua", "Judg": "judges", "Ruth": "ruth",
    "1Sam": "1-samuel", "2Sam": "2-samuel", "1Kgs": "1-kings", "2Kgs": "2-kings",
    "1Chr": "1-chronicles", "2Chr": "2-chronicles", "Ezra": "ezra", "Neh": "nehemiah",
    "Esth": "esther", "Job": "job", "Ps": "psalms", "Prov": "proverbs",
    "Eccl": "ecclesiastes", "Song": "song-of-solomon", "Isa": "isaiah", "Jer": "jeremiah",
    "Lam": "lamentations", "Ezek": "ezekiel", "Dan": "daniel",
    "Hos": "hosea", "Joel": "joel", "Amos": "amos", "Obad": "obadiah",
    "Jonah": "jonah", "Mic": "micah", "Nah": "nahum", "Hab": "habakkuk",
    "Zeph": "zephaniah", "Hag": "haggai", "Zech": "zechariah", "Mal": "malachi",
    "Matt": "matthew", "Mark": "mark", "Luke": "luke", "John": "john",
    "Acts": "acts", "Rom": "romans",
    "1Cor": "1-corinthians", "2Cor": "2-corinthians",
    "Gal": "galatians", "Eph": "ephesians", "Phil": "philippians", "Col": "colossians",
    "1Thess": "1-thessalonians", "2Thess": "2-thessalonians",
    "1Tim": "1-timothy", "2Tim": "2-timothy", "Titus": "titus", "Phlm": "philemon",
    "Heb": "hebrews", "Jas": "james",
    "1Pet": "1-peter", "2Pet": "2-peter",
    "1John": "1-john", "2John": "2-john", "3John": "3-john",
    "Jude": "jude", "Rev": "revelation",
}

ALL_BOOKS = [
    "Gen","Exod","Lev","Num","Deut","Josh","Judg","Ruth",
    "1Sam","2Sam","1Kgs","2Kgs","1Chr","2Chr","Ezra","Neh",
    "Esth","Job","Ps","Prov","Eccl","Song","Isa","Jer","Lam",
    "Ezek","Dan","Hos","Joel","Amos","Obad","Jonah","Mic",
    "Nah","Hab","Zeph","Hag","Zech","Mal",
    "Matt","Mark","Luke","John","Acts","Rom","1Cor","2Cor","Gal",
    "Eph","Phil","Col","1Thess","2Thess","1Tim","2Tim","Titus",
    "Phlm","Heb","Jas","1Pet","2Pet","1John","2John","3John","Jude","Rev",
]

API_BASE = "https://api.midvash.com/v1/nlt"


def get_chapter_counts():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT book_code, MAX(chapter) FROM strong_en GROUP BY book_code ORDER BY book_code"
    )
    counts = {}
    for r in cur.fetchall():
        book_code, max_ch = r[0], r[1]
        cur2 = conn.execute(
            "SELECT chapter, MAX(verse) FROM strong_en WHERE book_code=? GROUP BY chapter ORDER BY chapter",
            (book_code,)
        )
        ch_verses = {}
        for r2 in cur2.fetchall():
            ch_verses[r2[0]] = r2[1]
        counts[book_code] = ch_verses
    conn.close()
    return counts


def fetch_json(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BibleA1/1.0"})
            resp = urllib.request.urlopen(req, timeout=30)
            return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            print(f"  HTTP {e.code}: {url}", file=sys.stderr)
            return None
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            print(f"  Error: {e}: {url}", file=sys.stderr)
            return None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--books", nargs="*", help="Books to import (default: all)")
    args = parser.parse_args()
    book_codes = args.books if args.books else ALL_BOOKS
    chapter_verses = get_chapter_counts()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strong_nlt (
            book_code TEXT,
            chapter INTEGER,
            verse INTEGER,
            text TEXT,
            PRIMARY KEY (book_code, chapter, verse)
        )
    """)
    total = conn.execute("SELECT COUNT(*) FROM strong_nlt").fetchone()[0]
    already = set()
    for r in conn.execute("SELECT DISTINCT book_code, chapter FROM strong_nlt").fetchall():
        already.add((r[0], r[1]))
    if total > 0:
        print(f"  Found {total} existing NLT verses, skipping already-imported chapters", file=sys.stderr)

    for book_code in book_codes:
        slug = MIDVASH_SLUG.get(book_code)
        if not slug:
            print(f"  No slug for {book_code}, skipping", file=sys.stderr)
            continue
        if book_code not in chapter_verses:
            print(f"  No chapter data for {book_code}, skipping", file=sys.stderr)
            continue

        chapters = sorted(chapter_verses[book_code].keys())
        for ch in chapters:
            if (book_code, ch) in already:
                continue
            expected_verses = chapter_verses[book_code][ch]
            url = f"{API_BASE}/{slug}/{ch}"
            data = fetch_json(url)
            if data is None:
                print(f"  Failed to fetch {book_code} {ch}", file=sys.stderr)
                continue

            verses = data.get("data", {}).get("verses", [])
            if not verses:
                print(f"  Empty verses for {book_code} {ch}", file=sys.stderr)
                continue

            for vs_idx, text in enumerate(verses, 1):
                if vs_idx > expected_verses:
                    break
                if not text.strip():
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO strong_nlt (book_code, chapter, verse, text) VALUES (?, ?, ?, ?)",
                    (book_code, ch, vs_idx, text.strip()),
                )
                total += 1

            conn.commit()
            if total % 1000 == 0:
                print(f"  Progress: {total} verses imported", file=sys.stderr)

            time.sleep(0.05)

    conn.close()
    print(f"Imported {total} NLT verses", file=sys.stderr)


if __name__ == "__main__":
    main()
