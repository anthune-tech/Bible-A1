# Bible A1 — Architecture & Reference

## 1. System Architecture Diagram

```ascii
┌──────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                              │
│  https://bible.yourdomain.com                                    │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                    ┌────▼────┐
                    │Cloudflare│  (Optional CDN — caches static assets)
                    │  CDN     │
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │  NGINX   │  (Reverse proxy, SSL termination,
                    │          │   gzip, caching, keepalive)
                    └────┬────┘
                         │ :8000
                    ┌────▼────────────────────────────────────────┐
                    │         PYTHON SERVER (server.py)            │
                    │  ThreadingHTTPServer on 0.0.0.0:8000         │
                    │                                              │
                    │  ┌──────────────┐  ┌─────────────────────┐   │
                    │  │ API Routes   │  │ Static File Serving  │   │
                    │  │  /api/*      │  │  / → index.html      │   │
                    │  │  GET / POST  │  │  /admin → admin.html  │   │
                    │  └──────┬───────┘  └─────────────────────┘   │
                    │         │                                     │
                    │    ┌────▼────────┐                            │
                    │    │  SQLite DB  │  bible_strong.db           │
                    │    │  WAL mode   │  (read-heavy workload)     │
                    │    └─────────────┘                            │
                    └───────────────────────────────────────────────┘
                                      │
                    ┌──────────────────▼──────────────────────────┐
                    │              OLLAMA                           │
                    │  Local LLM (e.g. llama3.1:8b)                 │
                    │  http://localhost:11434/api/generate          │
                    │  Used for AI Bible Q&A chat                   │
                    └───────────────────────────────────────────────┘
```

### Request Flow (Bible verse lookup)

```
1. Browser: GET /api/query?book=John&chapter=3&verse=16
2. Nginx: receives on port 443, proxies to :8000
3. Server: BibleHandler.do_GET() routes to /api/query
4. Server: query_verse("John", 3, 16, 16, "kjv")
5. SQLite: SELECT from strong_en WHERE book_code='John' AND chapter=3 AND verse=16
6. SQLite: SELECT from strong_gr WHERE book_code='John' AND chapter=3 AND verse=16
7. Server: merges English text + Greek words_json → interlinear array
8. Server: strips Strong's tags for clean KJV text
9. Server: returns JSON {book, chapter, verses[{verse, reference, text, interlinear}]}
10. Nginx: proxies JSON response back to browser
11. Browser: renderPassage() builds HTML interlinear table + KJV text
```

---

## 2. Directory Structure

```
/media/azmarpop/DATA/MY_AI/Bible_A1/
│
├── server.py                      # HTTP server (API + static files)
│   ├── BibleHandler class         # Request handler (GET/POST routing)
│   ├── get_conn()                 # SQLite connection with WAL mode
│   ├── query_verse()              # Main interlinear query logic
│   ├── search_references()        # Admin reference search
│   ├── get_commentary()           # Commentary lookup
│   ├── _handle_ask()              # Ollama AI chat integration
│   └── main()                     # Entry point (port 8000 default)
│
├── bible.py                       # CLI interlinear viewer
│   ├── resolve_book()             # Book name aliases
│   ├── parse_ref()                # Parse "John 3:16" style references
│   ├── display_nt_interlinear()   # NT Greek table renderer
│   ├── display_ot_interlinear()   # OT Hebrew table renderer
│   └── main()                     # CLI entry point
│
├── bible_strong.db                # Main SQLite database
│   ├── strong_en                  # English KJV text with Strong's tags
│   ├── strong_gr                  # Greek NT words with Strong's, grammar
│   ├── strong_he                  # Hebrew OT words with Strong's, translit
│   ├── strong_id                  # Indonesian TB text
│   ├── bible_references           # Admin Q&A references
│   ├── bible_commentary           # Matthew Henry commentary
│   └── bible_tb                   # Additional TB data
│
├── bible.db                       # Legacy/supplementary database
│
├── static/
│   ├── index.html                 # Main web UI (789 lines)
│   │   ├── Book/Chapter/Verse selectors
│   │   ├── Interlinear table renderer
│   │   ├── AI Chat sidebar (English/Indonesian)
│   │   ├── Commentary sidebar
│   │   ├── Verse linkification
│   │   └── Dark theme (GitHub-style)
│   └── admin.html                 # References admin panel (233 lines)
│       ├── Add/Edit/Delete refs
│       └── Table listing all refs
│
├── data/
│   ├── kjv_*.json                 # KJV Bible book data (per-book JSON)
│   ├── gnt.flat.json              # Greek NT flat data
│   ├── bhs_strong.zip             # Hebrew BHS Strong's data (zip)
│   └── commentary/
│       ├── genesis.json           # Matthew Henry commentary per book
│       ├── matthew.json
│       └── ... (66 books total)
│
├── import_bible.py                # Import KJV into SQLite
├── import_commentary.py           # Import commentary JSON → SQLite
├── import_strongs.py              # Import Strong's + Greek/Hebrew → SQLite
├── import_tb.py                   # Import Indonesian TB → SQLite
├── repair_kjv.py                  # Utility: repair KJV data
├── start.sh                       # Quick start (kill old process + start server)
├── README.md                      # Basic usage guide
├── .gitignore                     # Ignores *.db, data/, __pycache__/
├── .downloads/                    # (this directory)
│   ├── bible-a1-documentation.md  # Full conversation + deployment guide
│   └── bible-a1-architecture.md   # Architecture reference
└── __pycache__/                   # Python bytecode (auto-generated)
```

---

## 3. Database Schema

### `strong_en` — English Text

| Column | Type | Description |
|---|---|---|
| `book_code` | TEXT | Book abbreviation (e.g. "Gen", "John") |
| `chapter` | INTEGER | Chapter number |
| `verse` | INTEGER | Verse number |
| `text` | TEXT | Verse text with Strong's tags: `word[H1234]` |
| PRIMARY KEY | (book_code, chapter, verse) | |

### `strong_he` — Hebrew OT Words

| Column | Type | Description |
|---|---|---|
| `book_code` | TEXT | Book abbreviation |
| `chapter` | INTEGER | Chapter number |
| `verse` | INTEGER | Verse number |
| `words_json` | TEXT | JSON array of word objects |
| PRIMARY KEY | (book_code, chapter, verse) | |

Each word in `words_json`:
```json
{
  "strong": "7225",
  "he": "רֵאשִׁית",
  "translit": "rē·šîṯ",
  "definition": "beginning, chief"
}
```

### `strong_gr` — Greek NT Words

| Column | Type | Description |
|---|---|---|
| `book_code` | TEXT | Book abbreviation |
| `chapter` | INTEGER | Chapter number |
| `verse` | INTEGER | Verse number |
| `words_json` | TEXT | JSON array of word objects |
| PRIMARY KEY | (book_code, chapter, verse) | |

Each word in `words_json`:
```json
{
  "strong": "3056",
  "gr": "λόγος",
  "translit": "logos",
  "definition": "word, speech, message",
  "grammar": "N-NSM"
}
```

### `strong_id` — Indonesian TB Text

| Column | Type | Description |
|---|---|---|
| `book_code` | TEXT | Book abbreviation |
| `chapter` | INTEGER | Chapter number |
| `verse` | INTEGER | Verse number |
| `text` | TEXT | Verse text (same format as strong_en) |
| PRIMARY KEY | (book_code, chapter, verse) | |

### `bible_references` — Curated Q&A

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-increment primary key |
| `question` | TEXT | User question |
| `answer` | TEXT | Curated answer |
| `book` | TEXT | Optional linked book |
| `chapter` | INTEGER | Optional linked chapter |
| `verse_start` | INTEGER | Optional linked verse start |
| `verse_end` | INTEGER | Optional linked verse end |
| `created_at` | TEXT | Auto-set creation timestamp |
| `updated_at` | TEXT | Auto-set update timestamp |

### `bible_commentary` — Matthew Henry Commentary

| Column | Type | Description |
|---|---|---|
| `book_code` | TEXT | Book abbreviation |
| `chapter` | INTEGER | Chapter number |
| `verse_start` | INTEGER | Optional verse range start |
| `verse_end` | INTEGER | Optional verse range end |
| `verse_range` | TEXT | Verse reference label |
| `commentary_text` | TEXT | Full commentary text |

### `bible_tb` — Additional TB Data

| Column | Type | Description |
|---|---|---|
| `book_code` | TEXT | Book abbreviation |
| `chapter` | INTEGER | Chapter number |
| `verse` | INTEGER | Verse number |
| `text` | TEXT | Verse text (TB/Indonesian) |
| PRIMARY KEY | (book_code, chapter, verse) | (inferred) |

---

## 4. API Reference

### GET /api/books

Returns list of available book codes.

```
GET /api/books
Response: ["Gen", "Exod", "Lev", ..., "Rev"]
```

### GET /api/chapters

Returns list of chapter numbers for a book.

| Param | Type | Required | Description |
|---|---|---|---|
| `book` | string | ✅ | Book code (e.g. "Gen") |

```
GET /api/chapters?book=John
Response: [1, 2, 3, ..., 21]
```

### GET /api/verses

Returns list of verse numbers for a chapter.

| Param | Type | Required | Description |
|---|---|---|---|
| `book` | string | ✅ | Book code |
| `chapter` | integer | ✅ | Chapter number |

```
GET /api/verses?book=John&chapter=3
Response: [1, 2, 3, ..., 36]
```

### GET /api/query

Returns interlinear data for a verse or verse range.

| Param | Type | Required | Description |
|---|---|---|---|
| `book` | string | ✅ | Book code |
| `chapter` | integer | ✅ | Chapter number |
| `verse` | string | ✅ | Verse or range (e.g. "16" or "22-24") |
| `version` | string | ❌ | "kjv" (default) or "tb" |

```
GET /api/query?book=John&chapter=3&verse=16
```

```json
{
  "book": "John",
  "chapter": 3,
  "verses": [
    {
      "verse": 16,
      "reference": "John 3:16",
      "text": "For God so loved the world...",
      "language": "Greek",
      "interlinear": [
        {
          "strong": "G3779",
          "transliteration": "houtōs",
          "original": "Οὕτως",
          "gloss": "so",
          "grammar": "ADV"
        },
        {
          "strong": "G25",
          "transliteration": "ēgapēsen",
          "original": "ἠγάπησεν",
          "gloss": "loved",
          "grammar": "V-AAI-3S"
        }
      ]
    }
  ]
}
```

### GET /api/commentary

Returns commentary entries for a passage.

| Param | Type | Required | Description |
|---|---|---|---|
| `book` | string | ✅ | Book code |
| `chapter` | integer | ✅ | Chapter number |
| `verse` | string | ✅ | Verse number |

```
GET /api/commentary?book=John&chapter=3&verse=16
```

### GET /api/models

Returns available Ollama models.

```
GET /api/models
Response: ["llama3.1:8b", "llama3.2:3b", ...]
```

### GET /api/references

Returns all admin Q&A references.

```
GET /api/references
```

### POST /api/ask

Ask the AI Bible assistant.

| Param | Type | Required | Description |
|---|---|---|---|
| `question` | string | ✅ | User's question |
| `context` | string | ❌ | Current passage context |
| `model` | string | ❌ | Ollama model name (default: llama3.1:8b) |
| `lang` | string | ❌ | "en" or "id" (Indonesian) |

```
POST /api/ask
Content-Type: application/json

{"question": "What does faith mean?", "lang": "en"}
```

```json
{
  "answer": "Faith... [long response]",
  "tokens": 156
}
```

### POST /api/references

CRUD operations for admin references.

| Param | Type | Required | Description |
|---|---|---|---|
| `action` | string | ✅ | "add", "update", or "delete" |
| `question` | string | * | Question text |
| `answer` | string | * | Answer text |
| `book` | string | ❌ | Linked book code |

---

## 5. Data Flow: Verse Lookup (Detailed)

### Step-by-step for `GET /api/query?book=John&chapter=3&verse=16`

```
1. Do_GET() parses URL → book="John", chapter=3, verse="16"
2. query_verse("John", 3, 16, 16, "kjv")

2a. Determine testament:
    "John" in NT_SET → is_ot=False → orig_table="strong_gr"

2b. Query English text:
    SELECT chapter, verse, text FROM strong_en
    WHERE book_code='John' AND chapter=3 AND verse BETWEEN 16 AND 16

2c. Query original language:
    SELECT chapter, verse, words_json FROM strong_gr
    WHERE book_code='John' AND chapter=3 AND verse BETWEEN 16 AND 16

2d. For each verse (16):
    - Parse en_text: strip Strong's tags for clean KJV text
    - Parse words_json (JSON.parse → array of word objects)
    - Build interlinear array:
      For each word in orig_words:
        - Strong: "G{word.strong}"
        - transliteration: word.translit
        - original: word.gr
        - gloss: short_gloss(word.definition)
        - grammar: word.grammar

2e. Return JSON: {book, chapter, verses[{verse, reference, text, language, interlinear}]}

3. Browser receives JSON, renderPassage() builds:
   - Verse card header (reference + language badge)
   - Interlinear table (columns per word, rows per field)
   - KJV text below table
   - Verse navigation (prev/next)

4. Browser also calls loadCommentary() for the same verse
```

### OT vs NT Display

| Feature | NT (Greek) | OT (Hebrew) |
|---|---|---|
| Strong's prefix | `G` (e.g. G3056) | `H` (e.g. H7225) |
| Original field | `gr` (Greek script) | `he` (Hebrew script) |
| Transliteration | Yes | Yes |
| Grammar/morphology | Yes (e.g. V-AAI-3S) | No |
| Gloss | From definition field | From KJV Strong's mapping (word-by-word alignment) |

For OT, glosses are aligned by matching Strong's numbers between the Hebrew words and the English KJV text. If no Strong's match, falls back to `short_gloss()` on the definition field or word-position-based matching.

---

## 6. Components in Detail

### Interlinear Rendering

The interlinear table is the core UI component. Each **word** becomes a **column** in the table:

```ascii
┌─────────────────────────────────────────────────────┐
│ STRONG  │ G3779  │ G25    │ G846   │ G2889  │ ...  │
│ TRANS   │ houtōs │ ēgapēsen │      │ kosmon │ ...  │
│ ORIGINAL│ Οὕτως  │ ἠγάπησεν│ τὸν   │ κόσμον │ ...  │
│ GLOSS   │ so     │ loved   │ the   │ world  │ ...  │
│ GRAMMAR │ ADV    │ V-AAI-3S│ T-ASM │ N-ASM  │ ...  │
└─────────────────────────────────────────────────────┘
│ KJV: For God so loved the world...                   │
└─────────────────────────────────────────────────────┘
```

### AI Chat Flow

```
User asks question
        │
        ▼
Check admin references (POST /api/references/search)
        │
        ├── Found match?
        │   ├── YES → Display curated answer
        │   │         └── If linked verse → loadPassage(book, ch, vs)
        │   │
        │   └── NO  → Query Ollama (POST /api/ask)
        │               ├── Build system prompt (English or Indonesian)
        │               ├── Add passage context (if available)
        │               ├── Send to Ollama /api/generate
        │               └── Display model response + token count
        │
        ▼
Optional: Click linked Bible verse in AI response
        → searchFromLink() → loadPassage()
```

### Reference Search Algorithm

```python
search_references(question):
    # 1. Tokenize: extract words > 2 chars, stop words removed
    words = [w for w in re.findall(r"\w+", question)
             if len(w) > 2 and w.lower() not in STOP_WORDS]

    # 2. Build LIKE query: OR conditions for each word
    SELECT * FROM bible_references
    WHERE question LIKE '%word1%' OR question LIKE '%word2%' OR ...
    ORDER BY LENGTH(question) ASC
    LIMIT 5

    # 3. Score: count how many search words appear in each result
    threshold = max(1, len(words) // 2)

    # 4. Filter: only keep results with score >= threshold
    # 5. Sort: by score descending
```

### Ollama Integration

```python
_handle_ask(question, context, model, lang):

    # 1. Select system prompt template
    if lang == "id":
        prompt = "Anda adalah pengajar Alkitab..."
    else:
        prompt = "You are a Bible teacher..."

    # 2. Add passage context if provided
    if context:
        prompt += f"\nPassage context:\n{context}\n"

    # 3. Append user question
    prompt += f"\nQuestion: {question}\nAnswer:"

    # 4. POST to Ollama
    POST http://localhost:11434/api/generate
    {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 1024}
    }

    # 5. Parse response
    return {"answer": response_text, "tokens": eval_count}
```

### Commentary System

Commentary entries can cover:
- **Entire chapter** (verse_start IS NULL, verse_end IS NULL)
- **Book introduction** (chapter=0)
- **Chapter introduction** (verse_range='intro')
- **Specific verse range** (verse_start ≤ verse ≤ verse_end)

```sql
SELECT * FROM bible_commentary
WHERE book_code = ? AND chapter = ?
AND (verse_start IS NULL OR (verse_start <= ? AND verse_end >= ?))
ORDER BY verse_start ASC NULLS FIRST
```

### Short Gloss Algorithm

The `short_gloss()` function extracts a concise gloss from Strong's definitions:

```python
def short_gloss(defn, max_len=16):
    # 1. Split on commas/semicolons
    parts = re.split(r"[,;]", defn)

    # 2. Find first part that fits within max_len
    for p in parts:
        p2 = p.strip().strip(".,;:!?")
        if len(p2) <= max_len:
            return p2

    # 3. If none fit, truncate first part with "…"
    first = parts[0].strip().strip(".,;:!?")
    return first[:max_len-1] + "…"
```

---

## 7. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.1:8b` | Default model for AI chat |

Set via:
```bash
export OLLAMA_URL=http://192.168.1.100:11434
export OLLAMA_MODEL=llama3.2:3b
python3 server.py
```

Or in systemd service:
```
Environment="OLLAMA_URL=http://127.0.0.1:11434"
Environment="OLLAMA_MODEL=llama3.1:8b"
```

---

## 8. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Standard library only** | Zero dependencies — just `python3` and `sqlite3` (built-in). Works on any system without pip. |
| **ThreadingHTTPServer** | Lightweight, concurrent request handling. Sufficient for personal/small-group use. |
| **SQLite WAL mode** | Write-Ahead Logging for concurrent reads without lock contention. |
| **Separate tables for EN/GR/HE** | Clean separation of concerns. Each language has its own structure optimized for its data. |
| **Strong's-tagged English text** | Simple `word[H1234]` format in plaintext — easy to process with regex. |
| **Single-page frontend** | No build tools, no framework, no npm. Just one HTML file. |
| **Dark theme** | Easier on the eyes for extended Bible study. |
| **Indonesian support** | Serves Indonesian-speaking users with TB translation and Indonesian-language AI prompts. |

---

## 9. Performance Considerations

### Current Limitations

1. **SQLite is single-writer** — fine for read-heavy Bible lookups, but admin writes will briefly block reads
2. **No caching** — every API call hits SQLite (acceptable for personal use)
3. **Python stdlib HTTP** — no connection pooling, keepalive, or compression out of the box

### Recommended Optimizations

1. **Nginx reverse proxy** — handles TLS, compression, caching, keepalive
2. **Cloudflare CDN** — caches static HTML/CSS/JS at edge nodes
3. **SQLite indexes** — already covered by primary keys
4. **`PRAGMA cache_size=-64000`** — 64MB page cache
5. **`PRAGMA mmap_size=268435456`** — 256MB memory-mapped I/O
6. **In-memory verse cache** — optional: cache `query_verse()` results with LRU eviction

### Bottleneck Analysis

| Component | Bottleneck? | Fix |
|---|---|---|
| SQLite reads | ⚠️ At >100 concurrent users | Add read replicas or use PostgreSQL |
| Python GIL | ⚠️ At >50 concurrent API calls | Use gunicorn with multiple workers |
| Ollama inference | ✅ Slow by nature (3-10s per question) | Async processing + loading indicator |
| Static file serving | ✅ Solved by Nginx/Cloudflare | Skip Python entirely for static assets |
| Network bandwidth | ✅ Depends on your ISP upload speed | Cloudflare Tunnel offloads traffic |

---

*This document is part of the Bible A1 project. Last updated: July 2026.*
