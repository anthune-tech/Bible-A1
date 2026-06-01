# Bible Interlinear

Strong's-numbered interlinear Bible with KJV English, Greek (TR), and Hebrew (BHS).

## Usage

```bash
python3 server.py      # Start web UI + API on :8000
python3 bible.py John 3:16      # CLI interlinear
```

## API

```
GET /api/books                          # list all books
GET /api/chapters?book=Gen              # chapters for a book
GET /api/verses?book=Gen&chapter=1      # verses for a chapter
GET /api/query?book=John&chapter=3&verse=16        # single verse
GET /api/query?book=Gen&chapter=1&verse=1-5        # verse range
```

## Data Sources

- **KJV + Strong's**: [kaiserlik/kjv](https://github.com/kaiserlik/kjv)
- **Greek TR + Strong's**: [honza/textus-receptus](https://github.com/honza/textus-receptus)
- **Hebrew BHS + Strong's**: [eliranwong/BHS-Strong-no](https://github.com/eliranwong/BHS-Strong-no)
