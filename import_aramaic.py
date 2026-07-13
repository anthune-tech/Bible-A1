#!/usr/bin/env python3
"""Import Aramaic (Peshitta) NT from TheHolyAramaicScriptures.com into bible_strong.db.

Usage:  python3 import_aramaic.py
"""

import html
import re
import sqlite3
import sys
import urllib.request

DB_PATH = "bible_strong.db"
BASE = "https://theholyaramaicscriptures.weebly.com"

# (book_code, chapter_slug, num_chapters)
BOOKS = [
    ("Matt", "mat", 28),
    ("Mark", "mar", 16),
    ("Luke", "luk", 24),
    ("John", "joh", 21),
    ("Acts", "act", 28),
    ("Jas", "jam", 5),
    ("1Pet", "1-pet", 5),
    ("1John", "1-joh", 5),
    ("Rom", "rom", 16),
    ("1Cor", "1-cor", 16),
    ("2Cor", "2-cor", 13),
    ("Gal", "gal", 6),
    ("Eph", "eph", 6),
    ("Phil", "phil", 4),
    ("Col", "col", 4),
    ("1Thess", "i-thes", 5),
    ("2Thess", "i-i-thes", 3),
    ("1Tim", "i-tim", 6),
    ("2Tim", "i-i-tim", 4),
    ("Titus", "tit", 3),
    ("Phlm", "phi", 1),
    ("Heb", "heb", 13),
]


def extract_verses(html_text):
    """Extract verse-numbered English+Syriac text from the chapter HTML page."""
    m = re.search(
        r'<div[^>]*paragraph[^>]*>(.*?)</div>', html_text, re.DOTALL
    )
    if not m:
        return {}

    content = m.group(1)
    text = re.sub(r'<[^>]+>', '', content)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[\u200b\u200c\u200d\u2060\uFEFF]', '', text)

    verses = {}

    # The verse numbers appear in two formats:
    # 1. {DIGITS} like "{12}" (most chapters use this)
    # 2. Plain DIGITS preceded by Syriac text, followed by English (some chapters)
    # Some chapters mix both formats (e.g. Acts 8 uses plain for 1-38, {N} for 39-40)
    # So we need to use both patterns and merge.

    positions = {}

    # Pattern 1: {DIGITS}
    for m in re.finditer(r'\{(\d{1,3})\}', text):
        num = int(m.group(1))
        if 1 <= num <= 200:
            # Only keep the first (earliest) occurrence of each verse number
            if num not in positions:
                positions[num] = m.start()

    # Pattern 2: plain DIGITS preceded by Syriac or whitespace, followed by uppercase
    for m in re.finditer(r'(?:^|(?<=[\s\u0700-\u074F]))(\d{1,3})(?=\s+[A-Z"\'])', text):
        num = int(m.group(1))
        if 1 <= num <= 200:
            if num not in positions:
                positions[num] = m.start()

    if not positions:
        return {}

    # Sort by position
    sorted_pos = sorted(positions.items(), key=lambda x: x[1])

    items = list(sorted_pos)
    for i, (vnum, pos) in enumerate(items):
        # Find end of this verse's text
        if i + 1 < len(items):
            end = items[i + 1][1]
        else:
            end = len(text)

        # Find marker end — could be {DIGITS} or DIGITS
        idx = text.index(str(vnum), pos)
        marker_end = idx + len(str(vnum))
        if marker_end < len(text) and text[marker_end] == '}':
            marker_end += 1

        vs_text = text[marker_end:end].strip()
        vs_text = re.sub(r'\s*\{?\d{1,3}\}?\s*$', '', vs_text).strip()
        if vs_text:
            verses[vnum] = vs_text

    return verses


def fetch_chapter(slug, chapter):
    url = f"{BASE}/{slug}-{chapter}.html"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strong_arc (
            book_code TEXT,
            chapter INTEGER,
            verse INTEGER,
            text TEXT,
            PRIMARY KEY (book_code, chapter, verse)
        )
    """)
    total = 0

    for code, slug, chapters in BOOKS:
        for ch in range(1, chapters + 1):
            sys.stdout.write(f"  {code:5} {ch:2}... ")
            sys.stdout.flush()
            html_content = fetch_chapter(slug, ch)
            if not html_content:
                print("FAIL")
                continue

            verses = extract_verses(html_content)
            if not verses:
                print("no verses")
                continue

            for vnum in sorted(verses):
                text = verses[vnum]
                conn.execute(
                    "INSERT OR REPLACE INTO strong_arc (book_code, chapter, verse, text) VALUES (?, ?, ?, ?)",
                    (code, ch, vnum, text),
                )
                total += 1

            conn.commit()
            print(f"{len(verses):2}vs (v{min(verses)}-{max(verses)})")

    conn.close()
    print(f"\nDone. Imported {total} verses into strong_arc.")


if __name__ == "__main__":
    main()
