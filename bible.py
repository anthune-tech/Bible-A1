#!/usr/bin/env python3
"""Interlinear Bible CLI — BibleHub-style per-column output with Strong's, transliteration, grammar."""

import json
import os
import re
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "bible_strong.db")
OT_BOOKS = {
    "Gen","Exod","Lev","Num","Deut","Josh","Judg","Ruth",
    "1Sam","2Sam","1Kgs","2Kgs","1Chr","2Chr","Ezra","Neh",
    "Esth","Job","Ps","Prov","Eccl","Song","Isa","Jer","Lam",
    "Ezek","Dan","Hos","Joel","Amos","Obad","Jonah","Mic",
    "Nah","Hab","Zeph","Hag","Zech","Mal",
}
BOOK_ALIASES = {
    "genesis":"Gen","gen":"Gen","gn":"Gen",
    "exodus":"Exod","ex":"Exod",
    "leviticus":"Lev","lev":"Lev","lv":"Lev",
    "numbers":"Num","num":"Num","nm":"Num",
    "deuteronomy":"Deut","deut":"Deut","dt":"Deut",
    "joshua":"Josh","josh":"Josh","js":"Josh",
    "judges":"Judg","judg":"Judg","jdg":"Judg",
    "ruth":"Ruth","ru":"Ruth",
    "1samuel":"1Sam","1sam":"1Sam",
    "2samuel":"2Sam","2sam":"2Sam",
    "1kings":"1Kgs","1kgs":"1Kgs","1ki":"1Kgs",
    "2kings":"2Kgs","2kgs":"2Kgs","2ki":"2Kgs",
    "1chronicles":"1Chr","1chr":"1Chr","1ch":"1Chr",
    "2chronicles":"2Chr","2chr":"2Chr","2ch":"2Chr",
    "ezra":"Ezra","ezr":"Ezra",
    "nehemiah":"Neh","neh":"Neh",
    "esther":"Esth","esth":"Esth","es":"Esth",
    "job":"Job",
    "psalms":"Ps","psalm":"Ps","ps":"Ps",
    "proverbs":"Prov","prov":"Prov","pr":"Prov",
    "ecclesiastes":"Eccl","eccl":"Eccl","ecc":"Eccl",
    "songofsolomon":"Song","song":"Song","so":"Song",
    "isaiah":"Isa","isa":"Isa",
    "jeremiah":"Jer","jer":"Jer","jr":"Jer",
    "lamentations":"Lam","lam":"Lam",
    "ezekiel":"Ezek","ezek":"Ezek","ezk":"Ezek",
    "daniel":"Dan","dan":"Dan","dn":"Dan",
    "hosea":"Hos","hos":"Hos",
    "joel":"Joel","jl":"Joel",
    "amos":"Amos",
    "obadiah":"Obad","obad":"Obad",
    "jonah":"Jonah","jon":"Jonah",
    "micah":"Mic","mic":"Mic",
    "nahum":"Nah","nah":"Nah",
    "habakkuk":"Hab","hab":"Hab",
    "zephaniah":"Zeph","zeph":"Zeph",
    "haggai":"Hag","hag":"Hag",
    "zechariah":"Zech","zech":"Zech",
    "malachi":"Mal","mal":"Mal",
    "matthew":"Matt","matt":"Matt","mt":"Matt",
    "mark":"Mark","mk":"Mark",
    "luke":"Luke","lk":"Luke",
    "john":"John","jn":"John",
    "acts":"Acts",
    "romans":"Rom","rom":"Rom","rm":"Rom",
    "1corinthians":"1Cor","1cor":"1Cor",
    "2corinthians":"2Cor","2cor":"2Cor",
    "galatians":"Gal","gal":"Gal",
    "ephesians":"Eph","eph":"Eph",
    "philippians":"Phil","phil":"Phil",
    "colossians":"Col","col":"Col",
    "1thessalonians":"1Thess","1thess":"1Thess",
    "2thessalonians":"2Thess","2thess":"2Thess",
    "1timothy":"1Tim","1tim":"1Tim",
    "2timothy":"2Tim","2tim":"2Tim",
    "titus":"Titus","tit":"Titus",
    "philemon":"Phlm","phlm":"Phlm",
    "hebrews":"Heb","heb":"Heb",
    "james":"Jas","jas":"Jas",
    "1peter":"1Pet","1pet":"1Pet",
    "2peter":"2Pet","2pet":"2Pet",
    "1john":"1John","1john":"1John",
    "2john":"2John",
    "3john":"3John",
    "jude":"Jude",
    "revelation":"Rev","rev":"Rev",
}


def get_conn():
    if not os.path.exists(DB_PATH):
        print(f"Error: database not found at {DB_PATH}")
        print("Run 'python3 import_strongs.py' first.")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)


def resolve_book(book_str):
    key = book_str.strip().lower()
    if key in BOOK_ALIASES:
        return BOOK_ALIASES[key]
    return book_str.strip()


def parse_ref(ref):
    ref = ref.strip()
    m = re.match(r'(\d?\s*[A-Za-z]+)\s*(\d+):(\d+)(?:-(\d+))?$', ref)
    if not m:
        print(f"Error: could not parse reference '{ref}'")
        print("Usage: python bible.py <book> <chapter>:<verse>[-<verse>]")
        sys.exit(1)
    book_str = m.group(1).strip()
    chapter = int(m.group(2))
    start = int(m.group(3))
    end = int(m.group(4)) if m.group(4) else start
    return resolve_book(book_str), chapter, start, end


def short_gloss(defn, max_len=16):
    """Pick the best single-word/phrase gloss from a definition."""
    if not defn:
        return ""
    parts = re.split(r"[,;]", defn)
    for p in parts:
        p = p.strip().strip(".,;:!?")
        if not p:
            continue
        # Skip leading articles
            if p.startswith("the ") or p.startswith("an ") or p.startswith("a "):
                p = p[4:] if p.startswith("the ") else p[3:] if p.startswith("an ") else p[2:]
        # Skip "I " prefixes (verbs like "I beget")
        if p.startswith("I ") and len(p) <= 12:
            p = p[2:]
        words = p.split()
        # If it's a short phrase, keep it
        if len(words) <= 2:
            if len(p) <= max_len:
                return p
        # Single word that fits
        if len(words) == 1 and len(p) <= max_len:
            return p
    # Fallback: first word of first part
    first = parts[0].strip().strip(".,;:!?")
    fw = first.split()[0] if first.split() else first
    if len(fw) > max_len:
        fw = fw[:max_len-1] + "…"
    return fw


def render_cols(cols, labels_rows):
    """Render column data with word-wrap.

    cols: list of dicts, each with string fields
    labels_rows: list of (label, key) tuples
    """
    if not cols:
        return

    width = 120
    margin = 4

    # Compute widths
    n = len(cols)
    widths = []
    for i in range(n):
        w = max(len(str(cols[i].get(key, ""))) for _, key in labels_rows)
        widths.append(max(w + 1, 3))

    # Word-wrap groups
    groups = []
    cur = []
    cur_w = 0
    for i in range(n):
        w = widths[i]
        if cur and cur_w + w > width - margin:
            groups.append(cur)
            cur = []
            cur_w = 0
        cur.append(i)
        cur_w += w
    if cur:
        groups.append(cur)

    for grp in groups:
        for label, key in labels_rows:
            line = "  " + label + " " + "".join(
                str(cols[i].get(key, "")).ljust(widths[i]) for i in grp
            )
            print(line)
        print()


def display_nt_interlinear(rows, book_name, chapter, start_verse, end_verse):
    ref_range = f"{book_name} {chapter}:{start_verse}"
    if end_verse > start_verse:
        ref_range += f"-{end_verse}"
    print(f"\n{ref_range}\n")

    for (osis, ch, vs, en_text), (_, _, _, o_json) in rows:
        words = json.loads(o_json)

        cols = []
        for w in words:
            cols.append({
                "STR": f"G{w['strong']}",
                "TRL": w.get("translit", ""),
                "GR": w.get("gr", ""),
                "GL": short_gloss(w.get("definition", "")),
                "GRM": w.get("grammar", ""),
            })

        print(f"  v{vs}")
        render_cols(cols, [
            ("STR", "STR"), ("TRL", "TRL"),
            ("GR", "GR"), ("GL", "GL"), ("GRM", "GRM"),
        ])
        # Show full KJV verse
        if en_text:
            kjv_clean = re.sub(r"\[(G|H)\d+\]", "", en_text)
            print(f"  KJV {kjv_clean}")


def display_ot_interlinear(rows, book_name, chapter, start_verse, end_verse):
    ref_range = f"{book_name} {chapter}:{start_verse}"
    if end_verse > start_verse:
        ref_range += f"-{end_verse}"
    print(f"\n{ref_range}\n")

    for (osis, ch, vs, en_text), (_, _, _, o_json) in rows:
        words = json.loads(o_json)
        en_map = {}
        for m in re.finditer(r"([^\[\]]+?)\[((G|H)(\d+))\]", en_text):
            word = m.group(1).strip()
            strong = m.group(2)
            if word:
                en_map.setdefault(strong, []).append(word)

        en_used = {k: [False] * len(v) for k, v in en_map.items()}

        cols = []
        for w in words:
            sn = f"H{w['strong']}"
            gloss = ""
            if sn in en_map:
                glist = en_map[sn]
                for i, used in enumerate(en_used[sn]):
                    if not used:
                        gloss = glist[i]
                        en_used[sn][i] = True
                        break
                if not gloss and glist:
                    gloss = glist[0]
            if not gloss:
                gloss = short_gloss(w.get("definition", ""), 16)
            cols.append({
                "STR": sn,
                "HE": w.get("he", ""),
                "GL": gloss,
            })

        print(f"  v{vs}")
        render_cols(cols, [("STR", "STR"), ("HE", "HE"), ("GL", "GL")])
        if en_text:
            kjv_clean = re.sub(r"\[(G|H)\d+\]", "", en_text)
            print(f"  KJV {kjv_clean}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python bible.py <book> <chapter>:<verse>[-<verse>]")
        print("  Examples:")
        print("    python bible.py Eph 5:22-24")
        print("    python bible.py Gen 1:1-3")
        print("    python bible.py John 3:16")
        sys.exit(1)

    book_str = sys.argv[1]
    ref_part = sys.argv[2]
    full_ref = f"{book_str} {ref_part}"
    book_code, chapter, start, end = parse_ref(full_ref)

    conn = get_conn()
    is_ot = book_code in OT_BOOKS
    orig_table = "strong_he" if is_ot else "strong_gr"

    orig_rows = conn.execute(
        f"SELECT book_code, chapter, verse, words_json FROM {orig_table} "
        "WHERE book_code = ? AND chapter = ? AND verse BETWEEN ? AND ? "
        "ORDER BY verse",
        (book_code, chapter, start, end),
    ).fetchall()

    en_rows = conn.execute(
        "SELECT book_code, chapter, verse, text FROM strong_en "
        "WHERE book_code = ? AND chapter = ? AND verse BETWEEN ? AND ? "
        "ORDER BY verse",
        (book_code, chapter, start, end),
    ).fetchall()

    if not orig_rows and not en_rows:
        print(f"No data found for {book_code} {chapter}:{start}-{end}")
        sys.exit(1)

    en_by_verse = {}
    for r in en_rows:
        en_by_verse[(r[1], r[2])] = r
    orig_by_verse = {}
    for r in orig_rows:
        orig_by_verse[(r[1], r[2])] = r

    book_name = book_code
    combined = []
    for verse_num in range(start, end + 1):
        er = en_by_verse.get(
            (chapter, verse_num),
            (book_code, chapter, verse_num, "")
        )
        ow = orig_by_verse.get(
            (chapter, verse_num),
            (book_code, chapter, verse_num, "[]")
        )
        if ow[3] != "[]" or er[3]:
            combined.append((er, ow))

    if not combined:
        print(f"No data for {book_code} {chapter}:{start}-{end}")
        sys.exit(1)

    if is_ot:
        display_ot_interlinear(combined, book_name, chapter, start, end)
    else:
        display_nt_interlinear(combined, book_name, chapter, start, end)

    conn.close()


if __name__ == "__main__":
    main()
