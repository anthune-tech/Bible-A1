#!/usr/bin/env python3
"""Repair corrupt kaiserlik/kjv JSON files by extracting English text with regex."""

import json
import os
import re
import sqlite3

KJV_SRC = "/tmp/kjv_repo"
DB_PATH = os.path.join(os.path.dirname(__file__), "bible_strong.db")

OSIS_MAP = {
    "Gen":"Gen","Exo":"Exod","Lev":"Lev","Num":"Num","Deu":"Deut",
    "Jos":"Josh","Jdg":"Judg","Rth":"Ruth","1Sa":"1Sam","2Sa":"2Sam",
    "1Ki":"1Kgs","2Ki":"2Kgs","1Ch":"1Chr","2Ch":"2Chr","Ezr":"Ezra","Neh":"Neh",
    "Est":"Esth","Job":"Job","Psa":"Ps","Pro":"Prov","Ecc":"Eccl","Sng":"Song",
    "Isa":"Isa","Jer":"Jer","Lam":"Lam","Eze":"Ezek","Dan":"Dan",
    "Hos":"Hos","Joe":"Joel","Amo":"Amos","Oba":"Obad","Jon":"Jonah","Mic":"Mic",
    "Nah":"Nah","Hab":"Hab","Zep":"Zeph","Hag":"Hag","Zec":"Zech","Mal":"Mal",
    "Mat":"Matt","Mar":"Mark","Luk":"Luke","Jhn":"John","Act":"Acts","Rom":"Rom",
    "1Co":"1Cor","2Co":"2Cor","Gal":"Gal","Eph":"Eph","Phl":"Phil","Col":"Col",
    "1Th":"1Thess","2Th":"2Thess","1Ti":"1Tim","2Ti":"2Tim","Tit":"Titus","Phm":"Phlm",
    "Heb":"Heb","Jas":"Jas","1Pe":"1Pet","2Pe":"2Pet","1Jo":"1John","2Jo":"2John",
    "3Jo":"3John","Jde":"Jude","Rev":"Rev",
    "1 Chronicles":"1Chr","1 Corinthians":"1Cor","1 John":"1John","1 Kings":"1Kgs",
    "1 Peter":"1Pet","1 Samuel":"1Sam","1 Thessalonians":"1Thess","1 Timothy":"1Tim",
    "2 Chronicles":"2Chr","2 Corinthians":"2Cor","2 John":"2John","2 Kings":"2Kgs",
    "2 Peter":"2Pet","2 Samuel":"2Sam","2 Thessalonians":"2Thess","2 Timothy":"2Tim",
    "3 John":"3John","Acts":"Acts","Isaiah":"Isa","Mark":"Mark","Philemon":"Phlm",
}

CORRUPT_FILES = ["1Co.json", "1Ki.json", "2Ch.json", "Act.json", "Isa.json", "Mar.json", "Phm.json"]


def extract_en_verses(filepath):
    """Extract English text with Strong's from corrupt JSON.

    Strategy: find all "Book|Ch|Vs": { ... "en": "text...", ... } patterns
    where the "en" value contains Strong's tags [G####] or [H####].
    """
    with open(filepath, encoding="utf-8") as f:
        raw = f.read()

    # Extract OSIS code from verse keys (they use short codes like "1Co", "Gen")
    # The outer key may be a full name like "1 Corinthians"
    short_code_match = re.search(r'"([A-Za-z0-9]+)\|\d+\|\d+"\s*:\s*\{', raw[:2000])
    if not short_code_match:
        return []
    short_code = short_code_match.group(1)
    osis = OSIS_MAP.get(short_code, "")

    if not osis:
        # Fallback: try outer key
        book_match = re.match(r'\s*\{\s*"([^"]+)"', raw)
        if book_match:
            osis = OSIS_MAP.get(book_match.group(1), "")
    if not osis:
        return []

    verses = []

    # Find all verse keys (ShortCode|Ch|Vs)
    verse_key_pattern = re.compile(r'"' + re.escape(short_code) + r'\|(\d+)\|(\d+)"\s*:\s*\{')

    seen_keys = set()

    for m in verse_key_pattern.finditer(raw):
        ch = int(m.group(1))
        vs = int(m.group(2))
        key = (ch, vs)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        start = m.end()

        # Extract the "en" value by finding the field and its string value
        # The value starts after "en": " and goes until the next unescaped quote
        en_match = re.search(r'"en"\s*:\s*"(.*?)"(?=\s*[,}])', raw[start:], re.DOTALL)
        if en_match:
            en_text = en_match.group(1)
            # Unescape JSON escapes
            en_text = en_text.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
            # Check if it has Strong's tags
            if re.search(r'\[(G|H)\d+\]', en_text):
                verses.append((osis, ch, vs, en_text))

    return verses


def repair():
    conn = sqlite3.connect(DB_PATH)
    total = 0

    for fname in CORRUPT_FILES:
        fpath = os.path.join(KJV_SRC, fname)
        if not os.path.exists(fpath):
            print(f"  {fname}: not found")
            continue

        verses = extract_en_verses(fpath)
        if not verses:
            print(f"  {fname}: no verses extracted")
            continue

        inserted = 0
        for osis, chap, verse, en_text in verses:
            conn.execute(
                "INSERT OR REPLACE INTO strong_en (book_code, chapter, verse, text) VALUES (?, ?, ?, ?)",
                (osis, chap, verse, en_text),
            )
            inserted += 1
        total += inserted

        book_label = verses[0][0] if verses else fname
        print(f"  {fname} ({book_label}): {inserted} verses")

    conn.commit()
    conn.close()
    print(f"\nTotal verses recovered: {total}")


if __name__ == "__main__":
    repair()
