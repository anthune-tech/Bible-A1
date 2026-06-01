import json
import sqlite3
import sys
import os
import urllib.request
import urllib.error

DB_PATH = os.path.join(os.path.dirname(__file__), "bible.db")

VERSIONS = {
    "kjv": {
        "url": "https://raw.githubusercontent.com/midvash/bible-data/main/versions/en/kjv/books",
        "api": "https://api.github.com/repos/midvash/bible-data/contents/versions/en/kjv/books",
        "label": "English (KJV)",
    },
    "tr": {
        "url": "https://raw.githubusercontent.com/midvash/bible-data/main/versions/gr/tr/books",
        "api": "https://api.github.com/repos/midvash/bible-data/contents/versions/gr/tr/books",
        "label": "Greek (TR)",
    },
    "wlc": {
        "url": "https://raw.githubusercontent.com/midvash/bible-data/main/versions/he/wlc/books",
        "api": "https://api.github.com/repos/midvash/bible-data/contents/versions/he/wlc/books",
        "label": "Hebrew (WLC)",
    },
}


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "bible-importer/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def get_book_codes(api_url):
    data = fetch_json(api_url)
    return sorted(
        [entry["name"].replace(".json", "") for entry in data if entry["name"].endswith(".json")]
    )


def download_book(base_url, book_code):
    url = f"{base_url}/{book_code}.json"
    return fetch_json(url)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verses (
            version TEXT NOT NULL,
            book_code TEXT NOT NULL,
            book_name TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            text TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lookup ON verses(book_code, chapter, verse, version)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_version ON verses(version, book_code, chapter, verse)")
    conn.commit()
    return conn


def import_version(conn, version_key):
    info = VERSIONS[version_key]
    print(f"Fetching book list for '{version_key}' ({info['label']})...")
    book_codes = get_book_codes(info["api"])
    print(f"  Found {len(book_codes)} books")

    total_verses = 0
    for book_code in book_codes:
        print(f"  Downloading {book_code}...", end=" ", flush=True)
        try:
            data = download_book(info["url"], book_code)
        except Exception as e:
            print(f"FAILED: {e}")
            continue

        book_name = data.get("englishName", book_code)
        chapters = data.get("chapters", [])

        rows = []
        for ch in chapters:
            chap_num = ch["chapter"]
            for v in ch["verses"]:
                rows.append((version_key, book_code, book_name, chap_num, v["number"], v["text"]))

        conn.executemany(
            "INSERT INTO verses (version, book_code, book_name, chapter, verse, text) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        total_verses += len(rows)
        print(f"{len(rows)} verses")

    print(f"  Total: {total_verses} verses imported for '{version_key}'")
    return total_verses


def main():
    print(f"Bible SQLite database: {DB_PATH}")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Removed existing database")

    conn = init_db()

    total = 0
    for vkey in VERSIONS:
        total += import_version(conn, vkey)

    conn.close()
    print(f"\nDone! {total} total verses imported across {len(VERSIONS)} versions.")


if __name__ == "__main__":
    main()
