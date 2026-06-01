#!/usr/bin/env python3
"""Download Strong's-numbered Bible data and build alignment database.

Sources:
  - EN: kaiserklic/kjv (KJV + Strong's inline tags) - 59/66 valid files
  - GR: honza/textus-receptus (TR + Strong's per word)
  - HE: eliranwong/BHS-Strong-no (BHS + Strong's tab-separated CSV)
"""

import csv
import html
import json
import io
import os
import re
import sqlite3
import urllib.request
import zipfile

DB_PATH = os.path.join(os.path.dirname(__file__), "bible_strong.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
KJV_SRC = "/tmp/kjv_repo"
TR_URL = "https://raw.githubusercontent.com/honza/textus-receptus/master/data/gnt.flat.json"
BHS_ZIP_URL = "https://github.com/eliranwong/BHS-Strong-no/raw/master/BHS-with-Strong-no-extended.csv.zip"

BHS_NUM_TO_OSIS = [
    "Gen","Exod","Lev","Num","Deut","Josh","Judg","Ruth",
    "1Sam","2Sam","1Kgs","2Kgs","1Chr","2Chr","Ezra","Neh",
    "Esth","Job","Ps","Prov","Eccl","Song","Isa","Jer","Lam",
    "Ezek","Dan","Hos","Joel","Amos","Obad","Jonah","Mic",
    "Nah","Hab","Zeph","Hag","Zech","Mal",
]

# Full book names used as JSON outer keys in kaiserlik/kjv
FULL_NAME_MAP = {
    "1 Chronicles":"1Chr","1 Corinthians":"1Cor","1 John":"1John","1 Kings":"1Kgs",
    "1 Peter":"1Pet","1 Samuel":"1Sam","1 Thessalonians":"1Thess","1 Timothy":"1Tim",
    "2 Chronicles":"2Chr","2 Corinthians":"2Cor","2 John":"2John","2 Kings":"2Kgs",
    "2 Peter":"2Pet","2 Samuel":"2Sam","2 Thessalonians":"2Thess","2 Timothy":"2Tim",
    "3 John":"3John","Acts":"Acts","Isaiah":"Isa","Mark":"Mark","Philemon":"Phlm",
}

OSIS_MAP = {
    "Gen":"Gen","Exo":"Exod","Lev":"Lev","Num":"Num","Deu":"Deut",
    "Jos":"Josh","Jdg":"Judg","Rth":"Ruth",
    "1Sa":"1Sam","2Sa":"2Sam","1Ki":"1Kgs","2Ki":"2Kgs",
    "1Ch":"1Chr","2Ch":"2Chr","Ezr":"Ezra","Neh":"Neh",
    "Est":"Esth","Job":"Job","Psa":"Ps","Pro":"Prov",
    "Ecc":"Eccl","Sng":"Song",
    "Isa":"Isa","Jer":"Jer","Lam":"Lam","Eze":"Ezek",
    "Dan":"Dan","Hos":"Hos","Joe":"Joel","Amo":"Amos",
    "Oba":"Obad","Jon":"Jonah","Mic":"Mic","Nah":"Nah",
    "Hab":"Hab","Zep":"Zeph","Hag":"Hag","Zec":"Zech",
    "Mal":"Mal",
    "Mat":"Matt","Mar":"Mark","Luk":"Luke","Jhn":"John",
    "Act":"Acts","Rom":"Rom",
    "1Co":"1Cor","2Co":"2Cor","Gal":"Gal","Eph":"Eph",
    "Phl":"Phil","Col":"Col","1Th":"1Thess","2Th":"2Thess",
    "1Ti":"1Tim","2Ti":"2Tim","Tit":"Titus","Phm":"Phlm",
    "Heb":"Heb","Jas":"Jas","1Pe":"1Pet","2Pe":"2Pet",
    "1Jo":"1John","2Jo":"2John","3Jo":"3John","Jde":"Jude",
    "Rev":"Rev",
    **FULL_NAME_MAP,
}


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"  Already have {dest}")
        return
    print(f"  Downloading {url}")
    urllib.request.urlretrieve(url, dest)
    print(f"  -> {dest}")


def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strong_en (
            book_code TEXT,
            chapter INTEGER,
            verse INTEGER,
            text TEXT,
            PRIMARY KEY (book_code, chapter, verse)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strong_gr (
            book_code TEXT,
            chapter INTEGER,
            verse INTEGER,
            words_json TEXT,
            PRIMARY KEY (book_code, chapter, verse)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strong_he (
            book_code TEXT,
            chapter INTEGER,
            verse INTEGER,
            words_json TEXT,
            PRIMARY KEY (book_code, chapter, verse)
        )
    """)
    conn.commit()
    return conn


def import_kjv(conn):
    print("\n=== Importing KJV + Strong's ===")
    count = 0
    for fname in sorted(os.listdir(KJV_SRC)):
        if not fname.endswith(".json") or fname in ("books.json","chapter_count.json","lexicon.json"):
            continue
        fpath = os.path.join(KJV_SRC, fname)
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            print(f"  SKIP {fname} (corrupt JSON)")
            continue
        outer_key = next(iter(data.keys()))
        osis = OSIS_MAP.get(outer_key)
        if not osis:
            print(f"  Skipping {fname}: unknown OSIS code for '{outer_key}'")
            continue
        inner = data.get(outer_key, {})
        if not inner:
            continue
        for chap_key, chap_val in inner.items():
            if not isinstance(chap_val, dict):
                continue
            for verse_key, verse_val in chap_val.items():
                parts = verse_key.split("|")
                if len(parts) != 3:
                    continue
                ch, vs = int(parts[1]), int(parts[2])
                text = verse_val.get("en", "")
                if not text:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO strong_en VALUES (?, ?, ?, ?)",
                    (osis, ch, vs, text),
                )
                count += 1
    conn.commit()
    print(f"  Imported {count} KJV+Strong verses")


def import_tr(conn):
    print("\n=== Importing TR + Strong's ===")
    dest = os.path.join(DATA_DIR, "gnt.flat.json")
    download(TR_URL, dest)

    short_to_osis = {
        "MAT":"Matt","MRK":"Mark","LUK":"Luke","JHN":"John","ACT":"Acts",
        "ROM":"Rom","1CO":"1Cor","2CO":"2Cor","GAL":"Gal","EPH":"Eph",
        "PHP":"Phil","COL":"Col","1TH":"1Thess","2TH":"2Thess",
        "1TI":"1Tim","2TI":"2Tim","TIT":"Titus","PHM":"Phlm",
        "HEB":"Heb","JAS":"Jas","1PE":"1Pet","2PE":"2Pet",
        "1JN":"1John","2JN":"2John","3JN":"3John","JUD":"Jude","REV":"Rev",
    }

    count = 0
    with open(dest, encoding="utf-8") as f:
        data = json.load(f)

    for entry in data:
        osis = entry.get("book_name_osis", "")
        if not osis:
            osis = short_to_osis.get(entry.get("book_name_short", ""), "")
        if not osis:
            continue
        ch = entry["chapter"]
        vs = entry["verse"]
        words = entry.get("words", [])
        word_list = []
        for w in words:
            word_list.append({
                "gr": w.get("greek", ""),
                "strong": w.get("strong", 0),
                "translit": w.get("transliteration", ""),
                "grammar": w.get("grammar", ""),
                "definition": w.get("definition", ""),
            })
        conn.execute(
            "INSERT OR REPLACE INTO strong_gr VALUES (?, ?, ?, ?)",
            (osis, ch, vs, json.dumps(word_list, ensure_ascii=False)),
        )
        count += 1
    conn.commit()
    print(f"  Imported {count} TR+Strong verses")


def import_bhs(conn):
    print("\n=== Importing BHS + Strong's ===")
    zip_dest = os.path.join(DATA_DIR, "bhs_strong.zip")
    download(BHS_ZIP_URL, zip_dest)

    csv_name = None
    with zipfile.ZipFile(zip_dest) as zf:
        for n in zf.namelist():
            if n.endswith(".csv") and not n.startswith("__"):
                csv_name = n
                break
    if not csv_name:
        print("  No CSV found!")
        return

    verse_words = {}
    count = 0
    with zipfile.ZipFile(zip_dest) as zf:
        with zf.open(csv_name) as f:
            lines = f.read().decode("utf-8-sig").split("\n")
            for line in lines[1:]:  # skip header
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 4:
                    continue
                verse_id = parts[1].strip("〔〕")
                bhs_parts = verse_id.split("｜")
                if len(bhs_parts) < 4:
                    continue
                # Format: KJVverseID|book_num|chapter|verse
                book_num = int(bhs_parts[1]) - 1  # 0-indexed
                if book_num < 0 or book_num >= len(BHS_NUM_TO_OSIS):
                    continue
                osis = BHS_NUM_TO_OSIS[book_num]
                ch = int(bhs_parts[2])
                vs = int(bhs_parts[3])
                # Extract Hebrew word from BHSA (strip XML tags)
                bhs_xml = parts[2]
                he_word = re.sub(r"<[^>]+>", "", bhs_xml).strip()
                strong = parts[3].strip()
                try:
                    sn = int(strong.replace("H", "").replace("h", ""))
                except ValueError:
                    sn = 0
                key = (osis, ch, vs)
                if key not in verse_words:
                    verse_words[key] = []
                verse_words[key].append({"he": he_word, "strong": sn})

    for (osis, ch, vs), words in verse_words.items():
        conn.execute(
            "INSERT OR REPLACE INTO strong_he VALUES (?, ?, ?, ?)",
            (osis, ch, vs, json.dumps(words, ensure_ascii=False)),
        )
        count += 1
    conn.commit()
    print(f"  Imported {count} BHS+Strong verses")



def add_hebrew_defs(conn):
    """Add definitions and transliterations for common Strong's Hebrew words."""
    defs = {
        "853": "direct object marker; not translated",
        "3068": "LORD, YHWH, the proper name of God",
        "5921": "upon, on, over, above, against",
        "413": "to, toward, unto",
        "834": "who, which, that, because",
        "3605": "all, every, whole, everything",
        "559": "to say, speak, utter",
        "3808": "not, no, neither, never",
        "1121": "son, child, descendant, people",
        "3588": "for, because, that, since, when",
        "1961": "to be, become, exist, happen",
        "6213": "to do, make, accomplish, prepare",
        "430": "God, god, gods, divine being",
        "935": "to come, go, enter",
        "4428": "king, ruler",
        "3478": "Israel, the nation of Israel",
        "776": "earth, land, ground, country",
        "3117": "day, time, year",
        "6440": "face, presence, before, front",
        "1004": "house, household, family, temple",
        "5414": "to give, put, set, place",
        "376": "man, husband, person, mankind",
        "1931": "he, she, it, they, himself",
        "5971": "people, nation, population",
        "7523": "to murder, slay, kill",
        "5003": "to commit adultery",
        "1589": "to steal, carry away",
        "6030": "to answer, respond, bear witness",
        "8267": "false, deception, lies, deceitful",
        "5707": "witness, testimony, evidence",
        "4480": "from, out of, by, than, because of",
        "1697": "word, thing, matter, event, affair",
        "8085": "to hear, listen, obey, understand",
        "3045": "to know, perceive, understand, recognize",
        "6965": "to arise, stand up, stand, establish",
        "3212": "to go, walk, come, depart, proceed",
        "3548": "priest, minister, mediator",
        "5892": "city, town, dwelling",
        "3069": "Yah; shortened form of YHWH",
        "1696": "to speak, say, command, declare",
        "6944": "holy, sacred, set apart, sanctuary",
        "2896": "good, pleasant, beautiful, excellent",
        "1419": "great, large, important, mighty",
        "7311": "to lift up, exalt, raise, elevate",
        "6680": "to command, charge, ordain, appoint",
        "1288": "to bless, praise, salute",
        "3615": "to complete, finish, end, accomplish",
        "2142": "to remember, recall, mention",
        "7676": "sabbath, day of rest, cessation",
        "7651": "seven, seventh",
        "8337": "six, sixth",
        "5647": "to serve, work, labor, cultivate, worship",
        "7637": "seventh",
        "5375": "to lift up, bear, carry, take, forgive",
        "8034": "name, reputation, fame, memorial",
        "2617": "mercy, kindness, lovingkindness, faithfulness",
        "505": "thousand, family, clan, people",
        "1": "father, ancestor, chief, founder",
        "517": "mother, grandmother, matriarch",
        "3513": "to honor, glorify, respect, make heavy",
        "2530": "to desire, covet, delight in, long for",
        "7453": "neighbor, friend, companion, fellow",
        "2555": "violence, wrong, cruelty, injustice",
        "1497": "to steal, carry off, rob",
        "2403": "sin, transgression, offense, sin offering",
        "6588": "rebellion, transgression, trespass",
        "5771": "iniquity, guilt, punishment for sin",
        "3519": "glory, honor, abundance, splendor",
    }
    translit = {
        "430": "Elohim", "3068": "YHWH", "853": "eth", "5921": "al",
        "413": "el", "834": "asher", "3605": "kol", "559": "amar",
        "3808": "lo", "1121": "ben", "3588": "ki", "1961": "hayah",
        "6213": "asah", "935": "bo", "4428": "melek",
        "3478": "Yisrael", "776": "erets", "3117": "yom",
        "6440": "panim", "1004": "bayit", "5414": "natan",
        "376": "ish", "1931": "hu", "5971": "am",
        "7523": "ratsach", "5003": "na'af", "1589": "ganav",
        "6030": "anah", "8267": "sheqer", "5707": "ed",
        "4480": "min", "1697": "davar", "8085": "shama",
        "3045": "yada", "6965": "qum", "3212": "halak",
        "3548": "kohen", "5892": "ir", "1696": "dabar",
        "6944": "qodesh", "2896": "tov", "1419": "gadol",
        "1288": "barak", "5647": "avad", "5375": "nasa",
        "8034": "shem", "2617": "chesed", "505": "elef",
        "1": "av", "517": "em", "3513": "kavad",
        "7453": "rea", "2530": "chamad",
    }
    skipped = {"9000", "9009", "9005", "9003", "9004"}
    rows = conn.execute("SELECT rowid, words_json FROM strong_he").fetchall()
    updated = 0
    for rowid, wj in rows:
        words = json.loads(wj)
        changed = False
        for w in words:
            sn = str(w["strong"])
            if sn in skipped:
                continue
            if "definition" not in w and sn in defs:
                w["definition"] = defs[sn]
                changed = True
            if "translit" not in w and sn in translit:
                w["translit"] = translit[sn]
                changed = True
        if changed:
            conn.execute("UPDATE strong_he SET words_json=? WHERE rowid=?", (json.dumps(words, ensure_ascii=False), rowid))
            updated += 1
    conn.commit()
    print(f"  Added definitions/transliterations to {updated} Hebrew rows")

    # Create lookup table
    conn.execute("DROP TABLE IF EXISTS strong_defs")
    conn.execute("""
        CREATE TABLE strong_defs (
            strong TEXT PRIMARY KEY,
            definition TEXT NOT NULL,
            translit TEXT
        )
    """)
    for sn, defn in defs.items():
        conn.execute("INSERT OR REPLACE INTO strong_defs VALUES (?, ?, ?)",
                     (f"H{sn}", defn, translit.get(sn, "")))
    conn.commit()
    print(f"  Created strong_defs table with {len(defs)} entries")

def main():
    ensure_dir(DATA_DIR)

    if not os.path.exists(KJV_SRC):
        print("Cloning kaiserlik/kjv...")
        import subprocess
        subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/kaiserlik/kjv.git", KJV_SRC],
            check=True,
        )

    conn = init_db()
    import_kjv(conn)
    import_tr(conn)
    import_bhs(conn)
    add_hebrew_defs(conn)
    conn.close()

    print(f"\nDone! Database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    for table in ["strong_en", "strong_gr", "strong_he"]:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {cnt} verses")
    conn.close()


if __name__ == "__main__":
    main()
