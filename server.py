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
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

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


def query_verse(book_code, chapter, verse_start, verse_end):
    conn = get_conn()

    is_ot = book_code in OT_SET
    orig_table = "strong_he" if is_ot else "strong_gr"

    en_rows = conn.execute(
        "SELECT chapter, verse, text FROM strong_en "
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
            result = query_verse(book, chapter, vstart, vend)
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

        # Serve static files
        if path == "/" or path == "":
            self.path = "/index.html"
        elif path == "/admin" or path == "/admin.html":
            self.path = "/admin.html"
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
            if not question:
                self._error(400, "Missing question")
                return
            result = self._handle_ask(question, context, model)
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

        self._error(404, "Not found")

    def _handle_ask(self, question, context, model=None):
        model = model or OLLAMA_MODEL
        prompt = (
            "You are a Bible study assistant. Answer the user's question "
            "based on Scripture. Be concise (2-4 sentences). "
            "Always cite verses using this exact format: Book Chapter:Verse (e.g. Exodus 20:3, Romans 3:22-24). "
            "Use full book names (e.g. 'Exodus', '1 Corinthians') for clarity.\n"
        )
        if context:
            prompt += f"\nPassage context:\n{context}\n"
        prompt += f"\nQuestion: {question}\nAnswer:"

        try:
            req_body = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 512},
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
                return {"answer": "(No response from model)"}
            return {"answer": answer}
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
