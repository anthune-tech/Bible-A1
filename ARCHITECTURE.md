# Bible A1 — Architecture

## System Overview

```
Browser (React SPA)
       │
       │ HTTP :8000
       ▼
Python Server (server.py)
  ├── BibleHandler (SimpleHTTPRequestHandler)
  │     ├── GET  /api/books, /api/chapters, /api/verses, /api/query
  │     ├── GET  /api/commentary, /api/commentary/search, /api/commentary/sources
  │     ├── GET  /api/models
  │     ├── POST /api/ask → Ollama :11434
  │     └── GET  /* → serves static/ (SPA fallback to index.html)
  └── SQLite (bible_strong.db, WAL mode)
```

## Directory Structure

```
Bible_A1/
├── server.py                # HTTP server (988 lines) — all API + static serving
├── bible.py                 # CLI interlinear viewer
├── static/                  # Built frontend (output of npm run build)
│   ├── index.html
│   └── assets/index-*.js/css
├── src/                     # React 19 + TypeScript frontend source
│   ├── App.tsx              # Root: ThemeProvider → BrowserRouter → ChatProvider → Layout
│   ├── ChatContext.tsx       # Chat state with sessionStorage persistence
│   ├── ThemeContext.tsx      # Dark/light theme toggle
│   ├── api/client.ts        # Fetch wrappers for all API endpoints
│   ├── types/index.ts       # TypeScript interfaces
│   ├── components/Layout.tsx # Nav header (Bible | Commentary links)
│   ├── pages/BibleViewer.tsx # Main Bible page (574 lines)
│   └── pages/Commentary.tsx  # Commentary browser + search page
├── import_*.py              # Data import scripts
├── package.json             # Vite + React 19 + TypeScript
├── vite.config.ts           # Vite → static/ output
└── start.sh                 # Server launcher (prod + dev modes)
```

## Frontend Component Tree

```
App
├── ThemeProvider          (dark/light mode via localStorage)
│   └── BrowserRouter
│       └── ChatProvider   (sessionStorage-backed chat history)
│           └── Layout     (nav header)
│               └── Routes
│                   ├── BibleViewer    ("/")
│                   │     ├── Left sidebar: book/chapter/verse selects
│                   │     ├── Center: interlinear + commentary cards
│                   │     └── Right sidebar: AI chat panel
│                   └── Commentary     ("/commentary")
│                         ├── Browse tab: book/chapter/verse + commentaries
│                         └── Search tab: full-text commentary search
```

## Database Schema

### `strong_en` — English KJV with Strong's tags
| Column | Type | Notes |
|--------|------|-------|
| book_code | TEXT | "Gen", "John", ... |
| chapter | INTEGER | |
| verse | INTEGER | |
| text | TEXT | e.g. `In the beginning[H7225] God[H430] created[H1254] ...` |
| PK | (book_code,chapter,verse) | |

### `strong_he` — Hebrew OT words (BHS)
| Column | Type | Notes |
|--------|------|-------|
| book_code | TEXT | |
| chapter | INTEGER | |
| verse | INTEGER | |
| words_json | TEXT | `[{"strong":"7225","he":"רֵאשִׁית","translit":"rē·šîṯ","definition":"..."}, ...]` |
| PK | (book_code,chapter,verse) | |

### `strong_gr` — Greek NT words (TR)
| Column | Type | Notes |
|--------|------|-------|
| book_code | TEXT | |
| chapter | INTEGER | |
| verse | INTEGER | |
| words_json | TEXT | `[{"strong":"3056","gr":"λόγος","translit":"logos","definition":"...","grammar":"N-NSM"}, ...]` |
| PK | (book_code,chapter,verse) | |

### `strong_id` — Indonesian TB text
Same structure as `strong_en` with TB text.

### `strong_nlt` — NLT text
Same as `strong_en` with NLT text.

### `bible_commentary` — Matthew Henry / imported commentary
| Column | Description |
|--------|-------------|
| book_code | Book abbreviation |
| chapter | Chapter number |
| verse_start / verse_end | Verse range (nullable for chapter intro) |
| commentary_text | Full commentary text |

### `commentary_chunks` — Chunked commentary (full-text search)
| Column | Description |
|--------|-------------|
| source_abbr | Foreign key to commentary_sources |
| book_code, chapter, verse | Reference |
| chunk_text | Truncated text chunk |

### `commentary_sources` — Source metadata
| Column | Description |
|--------|-------------|
| abbr | Unique abbreviation (e.g. "mhc") |
| name | Full name |
| url | Source URL |

## Data Flow: Verse Lookup

```
GET /api/query?book=John&chapter=3&verse=16&version=kjv

1. query_verse("John", 3, 16, 16, "kjv")
2. Determine testament: "John" → NT → orig_table="strong_gr"
3. SELECT text FROM strong_en WHERE book_code='John' AND chapter=3 AND verse=16
4. SELECT words_json FROM strong_gr WHERE book_code='John' AND chapter=3 AND verse=16
5. Strip Strong's tags from English text for clean display
6. Parse words_json → interlinear array [{strong, original, translit, gloss, grammar}]
7. Return {book, chapter, verses[{verse, reference, text, language, interlinear}]}
```

## Data Flow: AI Chat

```
POST /api/ask {question, context?, model?, lang?}

1. Build system prompt (lang="en" or "id" for Indonesian)
2. Append passage context if provided
3. Search book chunks for relevant references (RAG)
4. Search commentary chunks for relevant commentary (RAG)
5. Append user question
6. POST to Ollama /api/generate with:
     model, prompt, stream=false,
     options: {num_predict: 4096, num_ctx: 8192}
7. Return {answer, tokens}
```

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Python stdlib only | Zero dependencies, works anywhere with Python 3 |
| SQLite WAL mode | Concurrent reads without lock contention |
| React + Vite frontend | Modern dev experience, fast builds, type-safe |
| ChatContext outside Routes | Chat history persists across page navigation |
| sessionStorage | Survives client-side nav, cleared on tab close |
