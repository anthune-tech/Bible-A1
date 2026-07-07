#!/usr/bin/env python3
"""Scrape NASB 1995 verse text from StudyLight.org into the Bible_A1 DB.

Usage:
  python3 import_nasb.py [--books Gen,Exod] [--delay 0.5]

Runs with a delay between requests to be respectful to StudyLight.
"""

import argparse
import http.cookiejar
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request

DB_PATH = os.path.join(os.path.dirname(__file__), "bible_strong.db")

BOOK_SLUG = {
    "Gen": "genesis", "Exod": "exodus", "Lev": "leviticus", "Num": "numbers",
    "Deut": "deuteronomy", "Josh": "joshua", "Judg": "judges", "Ruth": "ruth",
    "1Sam": "1-samuel", "2Sam": "2-samuel", "1Kgs": "1-kings", "2Kgs": "2-kings",
    "1Chr": "1-chronicles", "2Chr": "2-chronicles", "Ezra": "ezra", "Neh": "nehemiah",
    "Esth": "esther", "Job": "job", "Ps": "psalms", "Prov": "proverbs",
    "Eccl": "ecclesiastes", "Song": "songofsongs", "Isa": "isaiah", "Jer": "jeremiah",
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_opener = None


def _get_opener():
    global _opener
    if _opener is None:
        cj = http.cookiejar.CookieJar()
        _opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        _opener.open(urllib.request.Request("https://www.studylight.org/", headers=HEADERS), timeout=15)
    return _opener


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strong_nasb (
            book_code TEXT,
            chapter INTEGER,
            verse INTEGER,
            text TEXT,
            PRIMARY KEY (book_code, chapter, verse)
        )
    """)
    conn.commit()


def get_chapter_verse_counts(conn):
    c = conn.cursor()
    c.execute("""
        SELECT book_code, chapter, COUNT(*) as cnt
        FROM strong_en
        GROUP BY book_code, chapter
        ORDER BY book_code, chapter
    """)
    counts = {}
    for r in c.fetchall():
        counts.setdefault(r["book_code"], {})[r["chapter"]] = r["cnt"]
    return counts


def fetch_url(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = _get_opener().open(req, timeout=30)
            return resp.read().decode("utf-8", errors="replace")
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


def parse_verse_text(html):
    if not html:
        return None
    m = re.search(
        r'<div class="center-it fs-21 bold ptlrb20 mb20">\s*(.*?)<br\s*/?>\s*<span class="float-right italic fs-13">',
        html, re.DOTALL
    )
    if m:
        text = m.group(1).strip()
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    return None


def import_nasb(conn, book_list, delay=0.5, chapter_verses=None):
    c = conn.cursor()
    if chapter_verses is None:
        chapter_verses = get_chapter_verse_counts(conn)

    stats = {"pages": 0, "saved": 0, "errors": 0, "skipped": 0}

    for book_code in book_list:
        slug = BOOK_SLUG.get(book_code)
        if not slug:
            print(f"  Unknown book code: {book_code}", file=sys.stderr)
            continue
        if book_code not in chapter_verses:
            print(f"  No verse data for {book_code}, skipping", file=sys.stderr)
            continue

        chapters = sorted(chapter_verses[book_code].keys())
        for ch in chapters:
            max_verse = chapter_verses[book_code][ch]
            for vs in range(1, max_verse + 1):
                url = f"https://www.studylight.org/commentary/{slug}/{ch}-{vs}.html"
                stats["pages"] += 1

                if stats["pages"] > 1:
                    time.sleep(delay)

                html = fetch_url(url)
                if html is None:
                    stats["errors"] += 1
                    continue

                text = parse_verse_text(html)
                if text is None:
                    stats["errors"] += 1
                    continue

                c.execute(
                    "SELECT 1 FROM strong_nasb WHERE book_code=? AND chapter=? AND verse=?",
                    (book_code, ch, vs)
                )
                if c.fetchone():
                    stats["skipped"] += 1
                    continue

                c.execute(
                    "INSERT OR IGNORE INTO strong_nasb (book_code, chapter, verse, text) VALUES (?, ?, ?, ?)",
                    (book_code, ch, vs, text)
                )
                if c.rowcount:
                    stats["saved"] += 1

                conn.commit()

                if stats["pages"] % 100 == 0:
                    print(f"  Progress: {stats['pages']} pages, {stats['saved']} saved, {stats['skipped']} skipped",
                          file=sys.stderr)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import NASB 1995 from StudyLight.org")
    parser.add_argument("--books", help="Comma-separated book codes (e.g. Gen,Exod)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    args = parser.parse_args()

    conn = get_conn()
    init_table(conn)

    book_list = [b.strip() for b in args.books.split(",")] if args.books else ALL_BOOKS

    print(f"Starting NASB import for {len(book_list)} books: {', '.join(book_list)}", file=sys.stderr)
    print(f"Delay: {args.delay}s", file=sys.stderr)

    chapter_verses = get_chapter_verse_counts(conn)
    stats = import_nasb(conn, book_list, args.delay, chapter_verses)

    print(f"\nNASB import complete!", file=sys.stderr)
    print(f"  Pages fetched: {stats['pages']}", file=sys.stderr)
    print(f"  Verses saved: {stats['saved']}", file=sys.stderr)
    print(f"  Already existed: {stats['skipped']}", file=sys.stderr)
    print(f"  Errors: {stats['errors']}", file=sys.stderr)

    conn.close()


if __name__ == "__main__":
    main()
