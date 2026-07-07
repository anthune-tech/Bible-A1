#!/usr/bin/env python3
"""Scrape verse-by-verse commentary from StudyLight.org into the Bible_A1 DB.

Usage:
  python3 studylight_scraper.py [--books Gen,Exod] [--delay 1.0]
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
    "Acts": "acts", "Rom": "romans", "1Cor": "1-corinthians", "2Cor": "2-corinthians",
    "Gal": "galatians", "Eph": "ephesians", "Phil": "philippians", "Col": "colossians",
    "1Thess": "1-thessalonians", "2Thess": "2-thessalonians",
    "1Tim": "1-timothy", "2Tim": "2-timothy", "Titus": "titus", "Phlm": "philemon",
    "Heb": "hebrews", "Jas": "james", "1Pet": "1-peter", "2Pet": "2-peter",
    "1John": "1-john", "2John": "2-john", "3John": "3-john", "Jude": "jude", "Rev": "revelation",
}

COMMENTARY_NAMES = {
    "acc": "Adam Clarke Commentary",
    "bbc": "Bridgeway Bible Commentary",
    "bcc": "Coffman's Commentaries on the Bible",
    "bnb": "Barnes' Notes on the Whole Bible",
    "cal": "Calvin's Commentary on the Bible",
    "csc": "Smith's Bible Commentary",
    "dcc": "Dr. Constable's Expository Notes",
    "gbc": "Gann's Commentary on the Bible",
    "geb": "Gill's Exposition of the Whole Bible",
    "mhm": "Henry's Complete Commentary on the Bible",
    "wkc": "Kelly Commentary on Books of the Bible",
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


def init_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS commentary_sources (
            abbr TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT
        );
        CREATE TABLE IF NOT EXISTS commentary_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_abbr TEXT NOT NULL REFERENCES commentary_sources(abbr),
            book_code TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            UNIQUE(source_abbr, book_code, chapter, verse)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS commentary_chunks_fts USING fts5(
            chunk_text, source_abbr, book_code, chapter, verse
        );
    """)
    conn.commit()


def ensure_sources(conn):
    c = conn.cursor()
    for abbr, name in COMMENTARY_NAMES.items():
        c.execute("INSERT OR IGNORE INTO commentary_sources (abbr, name) VALUES (?, ?)", (abbr, name))
    conn.commit()


def get_chapter_verse_counts(conn):
    c = conn.cursor()
    c.execute("""
        SELECT book_code, chapter, COUNT(*) as cnt
        FROM strong_id
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


def parse_commentary_sections(html):
    if not html:
        return {}
    sections = {}
    seen_texts = {}
    anchor_re = re.compile(r'<a\s+name="verse-(\w+)"')
    for m in anchor_re.finditer(html):
        abbr = m.group(1)
        start = m.end()
        next_a = anchor_re.search(html, start)
        end = next_a.start() if next_a else len(html)
        content = html[start:end]
        text = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<div class="copyright"[^>]*>.*?</div>', '', text, flags=re.DOTALL)
        text = re.sub(r'<div class="biblio"[^>]*>.*?</div>', '', text, flags=re.DOTALL)
        text = re.sub(r'<div class="return-to-top-div[^>]*>.*?</div>', '', text, flags=re.DOTALL)
        text = re.sub(r'<a[^>]*>', '', text)
        text = re.sub(r'</a>', '', text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&#160;', ' ')
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) < 20:
            continue

        # Deduplicate per-abbr: skip if identical to last seen text
        if abbr in seen_texts and seen_texts[abbr] == text:
            continue
        seen_texts[abbr] = text
        sections[abbr] = text
    return sections


def rebuild_fts(conn):
    c = conn.cursor()
    c.execute("DELETE FROM commentary_chunks_fts")
    c.execute("""
        INSERT INTO commentary_chunks_fts(rowid, chunk_text, source_abbr, book_code, chapter, verse)
        SELECT id, chunk_text, source_abbr, book_code, chapter, verse
        FROM commentary_chunks
    """)
    conn.commit()


def import_commentaries(conn, book_list, delay=1.0, chapter_verses=None):
    c = conn.cursor()
    if chapter_verses is None:
        chapter_verses = get_chapter_verse_counts(conn)

    stats = {"pages": 0, "saved": 0, "errors": 0, "skipped": 0, "dedup": 0}

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

                sections = parse_commentary_sections(html)

                for abbr, text in sections.items():
                    c.execute(
                        "SELECT 1 FROM commentary_chunks WHERE source_abbr=? AND book_code=? AND chapter=? AND verse=?",
                        (abbr, book_code, ch, vs)
                    )
                    if c.fetchone():
                        stats["skipped"] += 1
                        continue

                    c.execute("""
                        INSERT OR IGNORE INTO commentary_chunks
                        (source_abbr, book_code, chapter, verse, chunk_text)
                        VALUES (?, ?, ?, ?, ?)
                    """, (abbr, book_code, ch, vs, text))
                    if c.rowcount:
                        stats["saved"] += 1

                conn.commit()

                if stats["pages"] % 100 == 0:
                    print(f"  Progress: {stats['pages']} pages, {stats['saved']} saved, {stats['skipped']} skipped",
                          file=sys.stderr)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Scrape StudyLight.org commentaries")
    parser.add_argument("--books", help="Comma-separated book codes (e.g. Gen,Exod)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    parser.add_argument("--rebuild-fts", action="store_true", help="Rebuild FTS index only")
    args = parser.parse_args()

    conn = get_conn()
    init_tables(conn)
    ensure_sources(conn)

    if args.rebuild_fts:
        print("Rebuilding FTS index...", file=sys.stderr)
        rebuild_fts(conn)
        print("Done.", file=sys.stderr)
        return

    book_list = [b.strip() for b in args.books.split(",")] if args.books else ALL_BOOKS

    print(f"Starting scrape for {len(book_list)} books: {', '.join(book_list)}", file=sys.stderr)
    print(f"Delay: {args.delay}s", file=sys.stderr)

    chapter_verses = get_chapter_verse_counts(conn)
    stats = import_commentaries(conn, book_list, args.delay, chapter_verses)

    print(f"\nScrape complete!", file=sys.stderr)
    print(f"  Pages fetched: {stats['pages']}", file=sys.stderr)
    print(f"  Sections saved: {stats['saved']}", file=sys.stderr)
    print(f"  Already existed: {stats['skipped']}", file=sys.stderr)
    print(f"  Errors: {stats['errors']}", file=sys.stderr)

    print("\nRebuilding FTS index...", file=sys.stderr)
    rebuild_fts(conn)
    print("Done!", file=sys.stderr)

    conn.close()


if __name__ == "__main__":
    main()
