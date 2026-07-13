import urllib.request
import re
import sqlite3
import sys

DB = "/media/azmarpop/DATA/MY_AI/Bible_A1/bible_strong.db"
BASE = "https://www.thearamaicscriptures.com"

BOOK_PAGES = {
    "Acts": "acts.html",
    "Matt": "matthews-gospel.html",
    "Mark": "marks-gospel.html",
    "Luke": "lukes-gospel.html",
    "John": "johns-gospel.html",
    "Rom": "romans.html",
    "1Cor": "1st-corinthians.html",
    "2Cor": "2nd-corinthians.html",
    "Gal": "galatians.html",
    "Eph": "ephesians.html",
    "Phil": "philippians.html",
    "Col": "colossians.html",
    "1Thess": "1st-thessalonians.html",
    "2Thess": "2nd-thessalonians.html",
    "1Tim": "1st-timothy.html",
    "2Tim": "2nd-timothy.html",
    "Titus": "titus.html",
    "Phlm": "philemon.html",
    "Heb": "hebrews.html",
    "Jas": "james.html",
    "1Pet": "1st-peter.html",
    "1John": "1st-john.html",
}

def get_visible_text(html):
    body = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
    if body:
        text = re.sub(r'<script[^>]*>.*?</script>', '', body.group(1), flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&#8203;', '', text)
        text = re.sub(r'\xa0', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&[a-z]+;', ' ', text, flags=re.I)
        # Decode numeric HTML entities to actual Unicode characters
        text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    return ""

def parse_book_page(html):
    text = get_visible_text(html)
    chapters = {}
    chapter_blocks = re.split(r'Chapter (\d+)', text)
    # chapter_blocks[0] = stuff before first chapter
    # chapter_blocks[1] = chapter number
    # chapter_blocks[2] = content for that chapter
    # ... alternating
    for i in range(1, len(chapter_blocks) - 1, 2):
        ch_num = int(chapter_blocks[i])
        block = chapter_blocks[i + 1] if i + 1 < len(chapter_blocks) else ""
        verses = parse_verses(block)
        chapters[ch_num] = verses
    return chapters

def parse_verses(block):
    verses = {}
    positions = []
    seen = set()

    # Match: verse_number optionally followed by {NN} then a word character
    # e.g. "1 {12} And..." or "2 up to..."
    for m in re.finditer(r'(\d+)\s+(?:\{\d+\}\s+)?(?=[A-Za-z])', block):
        vnum = int(m.group(1))
        if vnum not in seen:
            seen.add(vnum)
            positions.append((m.start(), vnum))

    positions.sort(key=lambda x: x[0])

    if not positions:
        return verses

    for i, (pos, vnum) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(block)
        # For verse 1, include text from block start (preceding Syriac)
        start = 0 if i == 0 else pos + len(str(vnum))
        vs_text = block[start:end].strip()
        # Strip leading {NN} or trailing raw digits that are not part of verse text
        vs_text = re.sub(r'^\s*\{\d+\}\s*', '', vs_text).strip()
        vs_text = re.sub(r'\s*\d+\s*$', '', vs_text).strip()
        if vs_text:
            verses[vnum] = vs_text

    return verses

def split_syriac_english(text):
    syriac = ''.join(ch for ch in text if 0x0700 <= ord(ch) <= 0x074F or ch == ' ')
    english = re.sub(r'[\u0700-\u074F]', '', text)
    # Strip leading verse number from English (there may be whitespace before it)
    english = re.sub(r'^\s*\d+\s*', '', english)
    english = re.sub(r'\s+', ' ', english).strip()
    syriac = re.sub(r'\s+', ' ', syriac).strip()
    return syriac, english


def import_book(book_code, url):
    print(f"\nFetching {url}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  FAILED: {e}")
        return 0
    
    chapters = parse_book_page(html)
    total = 0
    
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    
    for ch_num in sorted(chapters.keys()):
        vs_dict = chapters[ch_num]
        for vnum in sorted(vs_dict.keys()):
            raw = vs_dict[vnum]
            syriac, english = split_syriac_english(raw)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO strong_arc (book_code, chapter, verse, text, syriac) VALUES (?, ?, ?, ?, ?)",
                    (book_code, ch_num, vnum, english, syriac)
                )
                total += 1
            except Exception as e:
                print(f"  ERROR inserting {book_code} {ch_num}:{vnum}: {e}")
    
    conn.commit()
    conn.close()
    print(f"  {book_code}: {total} verses across {len(chapters)} chapters")
    return total

if __name__ == "__main__":
    total_all = 0
    for book_code, page in BOOK_PAGES.items():
        url = f"{BASE}/{page}"
        total_all += import_book(book_code, url)
    print(f"\nDone. Imported {total_all} verses total.")
