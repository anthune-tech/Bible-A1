#!/usr/bin/env python3
"""Bible Interlinear Server — API + Web UI.

Standard library only (no pip dependencies needed).

API endpoints:
  GET /api/query?book=Eph&chapter=5&verse=22-24
  GET /api/books
  GET /api/book/<code>

Web UI:  GET / (serves static/index.html)
"""

import json
import os
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")

DB_PATH = os.path.join(os.path.dirname(__file__), "bible_strong.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

OT_BOOKS = [
    "Gen","Exod","Lev","Num","Deut","Josh","Judg","Ruth",
    "1Sam","2Sam","1Kgs","2Kgs","1Chr","2Chr","Ezra","Neh",
    "Esth","Job","Ps","Prov","Eccl","Song","Isa","Jer","Lam",
    "Ezek","Dan","Hos","Joel","Amos","Obad","Jonah","Mic",
    "Nah","Hab","Zeph","Hag","Zech","Mal",
]
OT_SET = set(OT_BOOKS)

NT_BOOKS = [
    "Matt","Mark","Luke","John","Acts","Rom","1Cor","2Cor","Gal",
    "Eph","Phil","Col","1Thess","2Thess","1Tim","2Tim","Titus",
    "Phlm","Heb","Jas","1Pet","2Pet","1John","2John","3John","Jude","Rev",
]
NT_SET = set(NT_BOOKS)

# --- Helpers ---

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bible_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            book TEXT,
            chapter INTEGER,
            verse_start INTEGER,
            verse_end INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strong_id (
            book_code TEXT,
            chapter INTEGER,
            verse INTEGER,
            text TEXT,
            PRIMARY KEY (book_code, chapter, verse)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strong_nlt (
            book_code TEXT,
            chapter INTEGER,
            verse INTEGER,
            text TEXT,
            PRIMARY KEY (book_code, chapter, verse)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strong_nasb (
            book_code TEXT,
            chapter INTEGER,
            verse INTEGER,
            text TEXT,
            PRIMARY KEY (book_code, chapter, verse)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn TEXT,
            title TEXT NOT NULL,
            author TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS book_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            section TEXT DEFAULT '',
            chunk_text TEXT NOT NULL
        )
    """)
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS book_chunks_fts USING fts5(chunk_id, chunk_text)")
    except Exception:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS commentary_sources (
            abbr TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commentary_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_abbr TEXT NOT NULL REFERENCES commentary_sources(abbr),
            book_code TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            UNIQUE(source_abbr, book_code, chapter, verse)
        )
    """)
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS commentary_chunks_fts USING fts5(chunk_text, source_abbr, book_code, chapter, verse)")
    except Exception:
        pass

    try:
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    conn.commit()
    conn.close()


def short_gloss(defn, max_len=16):
    if not defn or not max_len:
        return ""
    parts = re.split(r"[,;]", defn)
    # Prefer first part that fits
    for p in parts:
        p2 = p.strip().strip(".,;:!?")
        if not p2:
            continue
        if len(p2) <= max_len:
            return p2
    # Truncate first part
    first = parts[0].strip().strip(".,;:!?")
    if len(first) <= max_len:
        return first
    return first[:max_len-1] + "…"


def parse_en_strong(text):
    results = []
    for m in re.finditer(r"([^\[\]]+?)\[((G|H)(\d+))\]", text):
        word = m.group(1).strip()
        strong = m.group(2)
        if word:
            results.append((word, strong))
    return results


# --- API Logic ---

def get_books():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT book_code FROM strong_en"
    ).fetchall()
    conn.close()
    avail = {r[0] for r in rows}
    result = []
    for b in OT_BOOKS + NT_BOOKS:
        if b in avail:
            result.append(b)
    return result


def get_chapters(book_code):
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT chapter FROM strong_en WHERE book_code = ? ORDER BY chapter",
        (book_code,),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_verses(book_code, chapter):
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT verse FROM strong_en WHERE book_code = ? AND chapter = ? ORDER BY verse",
        (book_code, chapter),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def query_verse(book_code, chapter, verse_start, verse_end, version="kjv"):
    conn = get_conn()

    is_ot = book_code in OT_SET
    orig_table = "strong_he" if is_ot else "strong_gr"

    en_table = {"kjv": "strong_en", "tb": "strong_id", "nlt": "strong_nlt", "nasb": "strong_nasb"}.get(version, "strong_en")
    en_rows = conn.execute(
        f"SELECT chapter, verse, text FROM {en_table} "
        "WHERE book_code = ? AND chapter = ? AND verse BETWEEN ? AND ? "
        "ORDER BY verse",
        (book_code, chapter, verse_start, verse_end),
    ).fetchall()

    orig_rows = conn.execute(
        f"SELECT chapter, verse, words_json FROM {orig_table} "
        "WHERE book_code = ? AND chapter = ? AND verse BETWEEN ? AND ? "
        "ORDER BY verse",
        (book_code, chapter, verse_start, verse_end),
    ).fetchall()

    en_by_verse = {}
    for r in en_rows:
        en_by_verse[(r[0], r[1])] = r[2]
    orig_by_verse = {}
    for r in orig_rows:
        orig_by_verse[(r[0], r[1])] = r[2]

    verses = []
    for vnum in range(verse_start, verse_end + 1):
        en_text = en_by_verse.get((chapter, vnum), "")
        ow_json = orig_by_verse.get((chapter, vnum), "[]")
        orig_words = json.loads(ow_json)

        interlinear = []
        if is_ot:
            en_map = {}
            for m in re.finditer(r"([^\[\]]+?)\[((G|H)(\d+))\]", en_text):
                word = m.group(1).strip()
                strong = m.group(2)
                if word:
                    en_map.setdefault(strong, []).append(word)
            en_used = {k: [False] * len(v) for k, v in en_map.items()}
            # Fallback: if no Strong's tags in English, match by word position
            fallback_en_words = None
            if not en_map:
                raw = re.sub(r"<[^>]+>", "", en_text)
                content = [w for w in re.findall(r"\w+", raw) if w.lower() not in STOP_WORDS]
                if content:
                    fallback_en_words = content
            for idx, w in enumerate(orig_words):
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
                if not gloss and fallback_en_words:
                    fi = idx - (len(orig_words) - len(fallback_en_words))
                    if fi >= 0 and fi < len(fallback_en_words):
                        gloss = fallback_en_words[fi]
                interlinear.append({
                    "strong": sn,
                    "original": w.get("he", ""),
                    "transliteration": w.get("translit", ""),
                    "gloss": gloss,
                })
        else:
            for w in orig_words:
                interlinear.append({
                    "strong": f"G{w['strong']}",
                    "transliteration": w.get("translit", ""),
                    "original": w.get("gr", ""),
                    "gloss": short_gloss(w.get("definition", "")),
                    "grammar": w.get("grammar", ""),
                })

        kjv_clean = re.sub(r"\[(G|H)\d+\]", "", en_text) if en_text else ""

        verses.append({
            "verse": vnum,
            "reference": f"{book_code} {chapter}:{vnum}",
            "text": kjv_clean,
            "language": "Hebrew" if is_ot else "Greek",
            "interlinear": interlinear,
        })

    conn.close()
    return {
        "book": book_code,
        "chapter": chapter,
        "verses": verses,
    }


# --- Reference System ---

STOP_WORDS = {"what","does","the","and","is","are","was","were","how","why","where","when","who","which","this","that","these","those","for","with","from","have","has","had","not","but","all","can","will","would","could","should","may","might","shall","do","did","done","being","been","get","got","gets","make","made","makes","know","known","knew","about","into","than","then","also","just","very","well","much","more","most","some","any","each","every","both","two","like","such","only","other","over","after","before","between","through","during","without","within","along","among","upon","because","even","still","too","yet","own","same","so","no","nor","off","down","up","out","on","in","at","by","as","an","or","if",
"thou","thee","thy","thine","ye","art","shalt","doth","hath","dost","didst","canst","wilt","wouldest","couldest","shouldest","mayest","mightest","unto","thence","wherefore","thereof","therein","thereunto","thereupon","hereof","herein","hereunto","whereof","wherein","whereunto","whereupon","whoso","whatsoever","whosoever","whensoever","wheresoever","howsoever"}

def search_references(question):
    conn = get_conn()
    words = [w.lower() for w in re.findall(r"\w+", question) if len(w) > 2 and w.lower() not in STOP_WORDS]
    if not words:
        conn.close()
        return []
    conditions = " OR ".join(["LOWER(question) LIKE ?" for _ in words])
    params = [f"%{w}%" for w in words]
    rows = conn.execute(
        f"SELECT * FROM bible_references WHERE {conditions} ORDER BY LENGTH(question) ASC LIMIT 5",
        params,
    ).fetchall()
    conn.close()
    results = []
    threshold = max(1, len(words) // 2)
    for r in rows:
        score = sum(1 for w in words if w in r["question"].lower())
        if score < threshold:
            continue
        results.append({
            "id": r["id"],
            "question": r["question"],
            "answer": r["answer"],
            "book": r["book"],
            "chapter": r["chapter"],
            "verse_start": r["verse_start"],
            "verse_end": r["verse_end"],
            "score": score,
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def get_all_references():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM bible_references ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_reference(question, answer, book=None, chapter=None, vstart=None, vend=None):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO bible_references (question, answer, book, chapter, verse_start, verse_end) VALUES (?, ?, ?, ?, ?, ?)",
        (question, answer, book, chapter, vstart, vend),
    )
    conn.commit()
    ref_id = cur.lastrowid
    conn.close()
    return ref_id


def update_reference(ref_id, question, answer, book=None, chapter=None, vstart=None, vend=None):
    conn = get_conn()
    conn.execute(
        "UPDATE bible_references SET question=?, answer=?, book=?, chapter=?, verse_start=?, verse_end=?, updated_at=datetime('now') WHERE id=?",
        (question, answer, book, chapter, vstart, vend, ref_id),
    )
    conn.commit()
    conn.close()


def delete_reference(ref_id):
    conn = get_conn()
    conn.execute("DELETE FROM bible_references WHERE id=?", (ref_id,))
    conn.commit()
    conn.close()


# --- Book Knowledge Base (RAG) ---

def import_book(isbn, title, author, sections):
    """Import a book with its content sections.
    sections: list of {"section": str, "text": str}
    """
    conn = get_conn()
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.execute(
            "INSERT INTO books (isbn, title, author) VALUES (?, ?, ?)",
            (isbn or None, title, author or ""),
        )
        book_id = cur.lastrowid

        for sec in sections:
            chunks = chunk_text(sec["text"])
            for chunk in chunks:
                conn.execute(
                    "INSERT INTO book_chunks (book_id, section, chunk_text) VALUES (?, ?, ?)",
                    (book_id, sec.get("section", ""), chunk),
                )

        # Sync FTS index
        try:
            conn.execute("INSERT INTO book_chunks_fts (chunk_id, chunk_text) SELECT id, chunk_text FROM book_chunks")
        except Exception:
            pass

        conn.commit()
        return book_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def chunk_text(text, max_chars=1000):
    """Split text into chunks by paragraphs, grouped to ~max_chars."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chunks = []
    current = []
    current_len = 0
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        p_len = len(p)
        if current_len + p_len > max_chars and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(p)
        current_len += p_len
    if current:
        chunks.append("\n\n".join(current))
    if not chunks:
        chunks = [text.strip()]
    return chunks


def search_book_chunks(query, limit=5):
    """Search book chunks using FTS5 (fallback: LIKE)."""
    conn = get_conn()
    try:
        try:
            rows = conn.execute(
                """SELECT bc.id, bc.book_id, bc.section, bc.chunk_text, b.title, b.author, b.isbn
                   FROM book_chunks_fts f
                   JOIN book_chunks bc ON bc.id = f.chunk_id
                   JOIN books b ON b.id = bc.book_id
                   WHERE book_chunks_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
        except Exception:
            # FTS5 fallback: simple LIKE search
            words = [w for w in re.findall(r"\w+", query) if len(w) > 2]
            if not words:
                return []
            conditions = " OR ".join(["bc.chunk_text LIKE ?" for _ in words])
            params = [f"%{w}%" for w in words]
            rows = conn.execute(
                f"""SELECT bc.id, bc.book_id, bc.section, bc.chunk_text, b.title, b.author, b.isbn
                    FROM book_chunks bc
                    JOIN books b ON b.id = bc.book_id
                    WHERE {conditions}
                    LIMIT ?""",
                params + [limit],
            ).fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "book_id": r[1],
                "section": r[2],
                "text": r[3],
                "book_title": r[4],
                "book_author": r[5],
                "isbn": r[6],
            }
            for r in rows
        ]
    except Exception:
        conn.close()
        return []


def get_all_books():
    conn = get_conn()
    rows = conn.execute(
        """SELECT b.*, COUNT(bc.id) as chunk_count
           FROM books b
           LEFT JOIN book_chunks bc ON bc.book_id = b.id
           GROUP BY b.id
           ORDER BY b.created_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_book(book_id):
    conn = get_conn()
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM book_chunks WHERE book_id=?", (book_id,))
        conn.execute("DELETE FROM books WHERE id=?", (book_id,))
        try:
                conn.execute("DELETE FROM book_chunks_fts WHERE chunk_id IN (SELECT id FROM book_chunks WHERE book_id=?)", (book_id,))
        except Exception:
            pass
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


# --- Commentary ---

def get_commentary(book_code, chapter, verse, include_studylight=False):
    conn = get_conn()
    result = []
    try:
        rows = conn.execute(
            """SELECT * FROM bible_commentary
               WHERE book_code = ? AND chapter = ?
               AND (verse_start IS NULL OR (verse_start <= ? AND verse_end >= ?))
               ORDER BY verse_start ASC NULLS FIRST""",
            (book_code, chapter, verse, verse),
        ).fetchall()
        result = [dict(r) for r in rows]
    except Exception:
        pass

    if include_studylight:
        sl_rows = conn.execute(
            """SELECT c.*, s.name as source_name
               FROM commentary_chunks c
               JOIN commentary_sources s ON s.abbr = c.source_abbr
               WHERE c.book_code = ? AND c.chapter = ? AND c.verse = ?
               ORDER BY c.source_abbr""",
            (book_code, chapter, verse),
        ).fetchall()
        for r in sl_rows:
            d = dict(r)
            d["source_type"] = "studylight"
            result.append(d)

    conn.close()
    return result


def search_commentary(query, limit=5):
    conn = get_conn()
    try:
        clean = " ".join(re.findall(r"\w+", query))
        if not clean:
            return []
        fts_query = " OR ".join(clean.split())
        rows = conn.execute(
            """SELECT f.rowid, f.chunk_text, f.source_abbr, f.book_code,
                      f.chapter, f.verse, s.name as source_name
               FROM commentary_chunks_fts f
               JOIN commentary_sources s ON s.abbr = f.source_abbr
               WHERE commentary_chunks_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (fts_query, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Build verse reference string
            book_name = d["book_code"]
            # Try to get full book name
            try:
                bn = conn.execute(
                    "SELECT book_name FROM bible_books WHERE book_code=?",
                    (d["book_code"],),
                ).fetchone()
                if bn:
                    book_name = bn["book_name"]
            except Exception:
                pass
            d["reference"] = f"{book_name} {d['chapter']}:{d['verse']}"
            result.append(d)
        return result
    except Exception as e:
        return [{"error": str(e)}]
    finally:
        conn.close()


def list_commentary_sources():
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT s.*, COUNT(c.id) as chunk_count
               FROM commentary_sources s
               LEFT JOIN commentary_chunks c ON c.source_abbr = s.abbr
               GROUP BY s.abbr
               ORDER BY s.abbr"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e)}]
    finally:
        conn.close()


class BibleHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # API routes
        if path == "/api/books":
            self._json_response(get_books())
            return

        if path == "/api/chapters":
            book = params.get("book", [""])[0]
            if not book:
                self._error(400, "Missing book param")
                return
            self._json_response(get_chapters(book))
            return

        if path == "/api/verses":
            book = params.get("book", [""])[0]
            ch_str = params.get("chapter", [""])[0]
            if not book or not ch_str:
                self._error(400, "Missing book/chapter params")
                return
            try:
                ch = int(ch_str)
            except ValueError:
                self._error(400, "Chapter must be an integer")
                return
            self._json_response(get_verses(book, ch))
            return

        if path == "/api/models":
            self._json_response(self._list_models())
            return

        if path.startswith("/api/query"):
            book = params.get("book", [""])[0]
            ch_str = params.get("chapter", [""])[0]
            vs_str = params.get("verse", [""])[0]
            if not book or not ch_str or not vs_str:
                self._error(400, "Missing required params: book, chapter, verse")
                return
            try:
                chapter = int(ch_str)
            except ValueError:
                self._error(400, "Chapter must be an integer")
                return
            vs_parts = vs_str.split("-")
            try:
                vstart = int(vs_parts[0])
                vend = int(vs_parts[1]) if len(vs_parts) > 1 else vstart
            except ValueError:
                self._error(400, "Verse must be an integer or range (e.g., 22-24)")
                return
            result = query_verse(book, chapter, vstart, vend, params.get("version", [""])[0] or "kjv")
            self._json_response(result)
            return

        if path == "/api/references":
            self._json_response(get_all_references())
            return

        if path == "/api/references/search":
            q = params.get("q", [""])[0]
            if not q:
                self._json_response([])
                return
            self._json_response(search_references(q))
            return

        if path == "/api/commentary":
            book = params.get("book", [""])[0]
            ch_str = params.get("chapter", [""])[0]
            vs_str = params.get("verse", [""])[0]
            if not book or not ch_str or not vs_str:
                self._error(400, "Missing book/chapter/verse params")
                return
            try:
                chapter = int(ch_str)
                verse = int(vs_str.split("-")[0])
            except ValueError:
                self._error(400, "Chapter and verse must be integers")
                return
            sl = params.get("studylight", [""])[0] in ("true", "1", "yes")
            self._json_response(get_commentary(book, chapter, verse, include_studylight=sl))
            return

        if path == "/api/commentary/search":
            q = params.get("q", [""])[0]
            if not q:
                self._json_response([])
                return
            self._json_response(search_commentary(q))
            return

        if path == "/api/commentary/sources":
            self._json_response(list_commentary_sources())
            return

        if path == "/api/books/list":
            self._json_response(get_all_books())
            return

        if path == "/api/books/search":
            q = params.get("q", [""])[0]
            if not q:
                self._json_response([])
                return
            self._json_response(search_book_chunks(q))
            return

        # SPA fallback: serve index.html for all non-API, non-file paths
        if not path.startswith("/api/"):
            try:
                translated = self.translate_path(self.path)
                if not os.path.isfile(translated):
                    self.path = "/index.html"
            except Exception:
                self.path = "/index.html"
        return super().do_GET()

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code, message):
        self._json_response({"error": message}, code)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._error(400, "Invalid JSON")
            return

        if path == "/api/ask":
            question = data.get("question", "").strip()
            context = data.get("context", "").strip()
            model = data.get("model", OLLAMA_MODEL).strip()
            lang = data.get("lang", "en").strip()
            if not question:
                self._error(400, "Missing question")
                return
            result = self._handle_ask(question, context, model, lang)
            self._json_response(result)
            return

        if path == "/api/references/search":
            q = data.get("question", "").strip()
            if not q:
                self._json_response([])
                return
            results = search_references(q)
            matched = [r for r in results if r["score"] > 0]
            if matched:
                self._json_response({"matched": True, "ref": matched[0]})
            else:
                self._json_response({"matched": False, "ref": None})
            return

        if path == "/api/references":
            action = data.get("action", "")
            if action == "add":
                ref_id = add_reference(
                    data.get("question", "").strip(),
                    data.get("answer", "").strip(),
                    data.get("book") or None,
                    data.get("chapter"),
                    data.get("verse_start"),
                    data.get("verse_end"),
                )
                self._json_response({"ok": True, "id": ref_id})
                return
            elif action == "update":
                update_reference(
                    data.get("id"),
                    data.get("question", "").strip(),
                    data.get("answer", "").strip(),
                    data.get("book") or None,
                    data.get("chapter"),
                    data.get("verse_start"),
                    data.get("verse_end"),
                )
                self._json_response({"ok": True})
                return
            elif action == "delete":
                delete_reference(data.get("id"))
                self._json_response({"ok": True})
                return

        if path == "/api/books/import":
            isbn = data.get("isbn", "").strip()
            title = data.get("title", "").strip()
            author = data.get("author", "").strip()
            content = data.get("content", "").strip()
            if not title or not content:
                self._error(400, "Missing title or content")
                return
            sections = data.get("sections", [])
            if not sections:
                sections = [{"section": "", "text": content}]
            try:
                book_id = import_book(isbn, title, author, sections)
                self._json_response({"ok": True, "id": book_id})
            except Exception as e:
                self._error(500, str(e))
            return

        if path == "/api/books/delete":
            book_id = data.get("id")
            if not book_id:
                self._error(400, "Missing book id")
                return
            delete_book(book_id)
            self._json_response({"ok": True})
            return

        self._error(404, "Not found")

    def _handle_ask(self, question, context, model=None, lang="en"):
        model = model or OLLAMA_MODEL
        if lang == "id":
            prompt = (
                "Anda adalah pengajar Alkitab yang berakar pada pandangan dunia historis alkitabiah. "
                "Alkitab adalah catatan sejarah yang benar dan berotoritas mengenai asal-usul bumi dan umat manusia — "
                "tidak ada sumber sejarah yang lebih tua atau lebih dapat diandalkan. "
                "Ajarkan generasi muda menggunakan penalaran filosofis yang berlandaskan Kitab Suci:\n"
                "1. Dasarkan setiap jawaban pada narasi Alkitab tentang penciptaan, kejatuhan, penebusan, dan pemulihan "
                "sebagai kerangka untuk memahami seluruh sejarah dan tujuan hidup manusia.\n"
                "2. Jelaskan bahwa manusia diciptakan Allah untuk memerintah dan mengelola bumi — "
                "untuk mengolah, memerintah, dan membawa keteraturan di bawah otoritas Allah (Kejadian 1:26-28).\n"
                "3. Gunakan narasi Alkitab sendiri untuk menjelaskan mengapa dunia seperti sekarang ini: "
                "penciptaan, kejatuhan, pencaran, umat perjanjian Allah, kedatangan Kristus, dan pengharapan pemulihan.\n"
                "4. Bernalar secara filosofis dari premis-premis Alkitab — "
                "tunjukkan hubungan logis antara apa yang dikatakan Kitab Suci dan apa artinya bagi cara kita hidup, berpikir, dan memahami dunia.\n"
                "5. Selalu kutip ayat dalam format: Kitab Pasal:Ayat (misalnya Kejadian 1:26, Roma 3:23). "
                "Gunakan nama kitab versi TB seperti 'Kejadian', 'Keluaran', '1 Korintus'.\n"
                "6. Bersikaplah mendalam seperti guru yang membentuk pikiran generasi muda.\n"
            )
        else:
            prompt = (
                "You are a Bible teacher rooted in the historical biblical worldview. "
                "The Bible is the true and authoritative record of Earth's and humanity's origins — "
                "there is no older or more reliable historical source. "
                "Teach the next generation using philosophical reasoning grounded in Scripture:\n"
                "1. Ground every answer in the biblical account of creation, fall, redemption, and restoration "
                "as the framework for understanding all of history and human purpose.\n"
                "2. Explain that humanity was designed by God to rule and steward the earth — "
                "to cultivate, govern, and bring order under God's authority (Genesis 1:26-28).\n"
                "3. Use the Bible's own narrative to explain why the world is the way it is: "
                "creation, the fall, the dispersion, God's covenant people, Christ's coming, and the hope of restoration.\n"
                "4. Reason philosophically from biblical premises — "
                "show logical connections between what Scripture says and what it means for how we live, think, and understand the world.\n"
                "5. Always cite verses in Book Chapter:Verse format (e.g. Exodus 20:3, Romans 3:22-24). "
                "Use full book names (e.g. 'Exodus', '1 Corinthians') for clarity.\n"
                "6. Be thorough like a teacher shaping young minds — not brief like a chatbot.\n"
            )
        if context:
            prompt += f"\nPassage context:\n{context}\n"

        # Retrieve relevant book knowledge
        try:
            chunks = search_book_chunks(question, limit=3)
            if chunks:
                book_ctx = "\n\nReferensi buku:\n"
                for c in chunks:
                    source = f"{c['book_title']}"
                    if c['book_author']:
                        source += f" oleh {c['book_author']}"
                    if c['section']:
                        source += f" — {c['section']}"
                    book_ctx += f"\n[{source}]\n{c['text'][:800]}\n"
                prompt += book_ctx
        except Exception:
            pass

        # Retrieve relevant commentary knowledge
        try:
            comm_chunks = search_commentary(question, limit=3)
            if comm_chunks:
                comm_ctx = "\n\nReferensi komentari:\n"
                for c in comm_chunks:
                    comm_ctx += f"\n[{c['source_name']} — {c['reference']}]\n{c['chunk_text'][:800]}\n"
                prompt += comm_ctx
        except Exception:
            pass

        prompt += f"\nQuestion: {question}\nAnswer:"

        try:
            req_body = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 4096, "num_ctx": 8192},
            }).encode()
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/generate",
                data=req_body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                result = json.loads(resp.read())
            answer = result.get("response", "").strip()
            if not answer:
                return {"answer": "(No response from model)", "tokens": 0}
            return {"answer": answer, "tokens": result.get("eval_count", 0)}
        except Exception as e:
            return {"answer": f"(Error querying AI: {e})"}

    def _list_models(self):
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def log_message(self, format, *args):
        msg = format % args if args else format
        print(f"[{self.log_date_time_string()}] {msg}")


def main():
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    # Create static directory if needed
    os.makedirs(STATIC_DIR, exist_ok=True)

    # Initialize database tables
    init_db()

    # Write a basic index.html if not present
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        print("Creating default UI...")

    print(f"Bible Interlinear Server starting on http://localhost:{port}")
    print(f"API: http://localhost:{port}/api/query?book=Eph&chapter=5&verse=22-24")
    print(f"Web: http://localhost:{port}/")
    print("Press Ctrl+C to stop")

    server = ThreadingHTTPServer(("0.0.0.0", port), BibleHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
