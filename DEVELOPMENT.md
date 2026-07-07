# Development & Maintenance

## Build

```bash
# Install Node.js 22+ (download prebuilt binary if not available)
curl -sL https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz -o /tmp/node.tar.xz
tar -xf /tmp/node.tar.xz -C /tmp/
export PATH="/tmp/node-v22.14.0-linux-x64/bin:$PATH"

npm install
npm run build    # tsc + vite → static/
```

Vite outputs to `static/`. The Python server serves these files from `static/`.

## Dev Server (Hot Reload)

```bash
./start.sh dev
```
- Vite dev server on :5173 (proxies `/api` to Python :8000)
- Python API server on :8000

## Verifying a Change

1. Rebuild: `npm run build`
2. Restart server: `kill $(lsof -t -i:8000) && python3 server.py`
3. Hard-refresh browser (Ctrl+F5)
4. To verify the new bundle is served, check `grep 'sessionStorage\|yourFeature' static/assets/index-*.js`

## Adding a New Database Table

1. Add `CREATE TABLE` in `server.py init_db()`
2. Add query functions in `server.py`
3. Add GET/POST route in `BibleHandler.do_GET()` / `do_POST()`
4. (Frontend) Add API function in `src/api/client.ts`
5. (Frontend) Add TypeScript type in `src/types/index.ts`

## Importing Bible Data

| Script | Source | Target Table |
|--------|--------|-------------|
| `import_bible.py` | `data/kjv_*.json` | `strong_en` |
| `import_strongs.py` | `data/gnt.flat.json`, `data/bhs_strong/` | `strong_gr`, `strong_he` |
| `import_tb.py` | Midvith API | `strong_id` |
| `import_nlt.py` | Midvash API | `strong_nlt` |
| `import_commentary.py` | `data/commentary/*.json` | `bible_commentary` + `commentary_chunks` |
| `studylight_scraper.py` | StudyLight.org | `commentary_chunks` |

## Common Issues & Debugging

### AI Chat Returns Truncated Answer
Increase `num_predict` in `server.py:_handle_ask()`. Default: `4096`. Context window is `8192`.

### NLT Missing Verses
NLT data from Midvash API has different versification than KJV. Some chapters have fewer verses. Manually insert missing verses via:
```sql
INSERT OR REPLACE INTO strong_nlt (book_code, chapter, verse, text)
VALUES ('Matt', 3, 17, '...');
```

### "No node found" During Build
Install Node.js binary:
```bash
curl -sL https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz -o /tmp/node.tar.xz
tar -xf /tmp/node.tar.xz -C /tmp/
export PATH="/tmp/node-v22.14.0-linux-x64/bin:$PATH"
```

### Chat History Lost on Navigation
- `ChatContext.tsx` wraps `Routes` in `App.tsx` — check it hasn't been moved inside `Routes`
- `ChatProvider` uses React state synced to `sessionStorage` — verify the `STORAGE_KEY` is consistent
- `sessionStorage` is cleared on tab close, but survives client-side route changes

### Database Lock Errors
Server uses WAL mode with `busy_timeout=5000`. If errors persist, check no other process has an open connection.

### Server Won't Start
- Check port 8000 isn't in use: `lsof -i:8000`
- Check `bible_strong.db` exists and is readable
- Run `python3 server.py` directly to see error output

## Linting

```bash
npm run lint   # oxlint — fast, no config needed
```

## Release Checklist

- [ ] `npm run build` succeeds
- [ ] `npm run lint` passes
- [ ] Server starts on :8000
- [ ] Bible page loads and verse query works
- [ ] Commentary page loads
- [ ] AI chat responds (Ollama must be running)
- [ ] Chat history persists across page navigation
- [ ] Version selector (KJV / TB / NLT) works
- [ ] Verse copying works
