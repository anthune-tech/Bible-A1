# Bible A1

Interlinear Bible web application — KJV + original Greek (TR) / Hebrew (BHS) with Strong's numbers, Indonesian TB/NLT translations, Matthew Henry commentary, and an AI Bible study assistant powered by Ollama.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3 (stdlib only — no pip) |
| HTTP Server | `ThreadingHTTPServer` on :8000 |
| Database | SQLite 3 (WAL mode) |
| Frontend | React 19 + TypeScript + Vite |
| AI Chat | Ollama (local LLM) |
| CLI | `python3 bible.py` |

## Quick Start

```bash
# Start server
python3 server.py

# Open http://localhost:8000
# Or use CLI:
python3 bible.py John 3:16
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/books` | All book codes |
| GET | `/api/chapters?book=Gen` | Chapters for a book |
| GET | `/api/verses?book=Gen&chapter=1` | Verses for a chapter |
| GET | `/api/query?book=John&chapter=3&verse=16&version=kjv` | Interlinear verse data |
| GET | `/api/commentary?book=John&chapter=3&verse=16` | Commentary entries |
| GET | `/api/commentary/search?q=faith` | Search commentary |
| GET | `/api/commentary/sources` | Available commentary sources |
| GET | `/api/models` | Available Ollama models |
| POST | `/api/ask` | AI chat query `{question, context?, model?, lang?}` |

## Frontend Development

```bash
# Requires Node.js 22+
npm install

# Dev server with hot reload (API proxied to :8000)
./start.sh dev

# Production build → static/
npm run build
```

## Data Sources

- **KJV + Strong's**: [kaiserlik/kjv](https://github.com/kaiserlik/kjv)
- **Greek TR + Strong's**: [honza/textus-receptus](https://github.com/honza/textus-receptus)
- **Hebrew BHS + Strong's**: [eliranwong/BHS-Strong-no](https://github.com/eliranwong/BHS-Strong-no)
- **Indonesian TB**: [midvith](https://midvith.github.io/bible) API
- **NLT**: Midvash API
- **Commentary**: Matthew Henry's Complete Commentary, StudyLight.org
