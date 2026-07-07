# Bible A1 — Full Documentation

## 1. Project Overview

**Bible A1** is an Interlinear Bible web application and CLI tool. It displays the King James Version (KJV) Bible alongside the original Greek (Textus Receptus) and Hebrew (BHS) texts with Strong's numbers, transliteration, glosses, and grammar. It also includes Matthew Henry's Complete Commentary, an AI Bible study assistant (via Ollama), and an admin panel for curated Q&A references.

### Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3 (standard library only — no pip deps) |
| HTTP Server | `http.server.ThreadingHTTPServer` |
| Database | SQLite 3 (WAL mode) |
| Frontend | Vanilla HTML + CSS + JavaScript (single-page app) |
| AI Chat | Ollama (local LLM, e.g. llama3.1:8b) |
| Commentary | Matthew Henry's Complete Commentary (Public Domain) |
| CLI | Python 3 script (`bible.py`) |

### Features

- Interlinear Bible display (Strong's, transliteration, original language, gloss, grammar)
- KJV English + original Greek/Hebrew texts
- Indonesian TB (Terjemahan Baru) version support
- AI Bible study Q&A chatbot (English or Indonesian)
- Matthew Henry's Commentary sidebar
- Admin-managed Q&A reference system
- RESTful API for all data
- Zero external Python dependencies

---

## 2. Codebase Analysis

### Directory Structure

```
Bible_A1/
├── server.py              # HTTP server — API + static file serving on :8000
├── bible.py               # CLI interlinear Bible viewer
├── bible_strong.db        # Main SQLite database (KJV + Greek + Hebrew + Strong's)
├── bible.db               # Indonesian TB database
├── import_bible.py        # Script to import KJV Bible data
├── import_commentary.py   # Script to import Matthew Henry's Commentary
├── import_strongs.py      # Script to import Strong's numbers data
├── import_tb.py           # Script to import Indonesian TB data
├── repair_kjv.py          # Utility to repair KJV data
├── start.sh               # Quick start script for server + Ollama
├── README.md              # Basic project README
├── .gitignore             # Git ignore rules
├── data/                  # Raw JSON data files
│   ├── kjv_*.json         # KJV books by chapter
│   ├── gnt.flat.json      # Greek NT flat data
│   └── commentary/        # Matthew Henry commentary per book
├── static/                # Static web files
│   ├── index.html         # Main single-page web UI
│   └── admin.html         # References admin panel
└── __pycache__/           # Python bytecode cache
```

### server.py (624 lines)

The main HTTP server. Key components:

- **BibleHandler class** — extends `SimpleHTTPRequestHandler`, serves API at `/api/*` and static files
- **GET endpoints**: `/api/books`, `/api/chapters`, `/api/verses`, `/api/query`, `/api/references`, `/api/references/search`, `/api/commentary`, `/api/models`
- **POST endpoints**: `/api/ask` (AI chat), `/api/references/search`, `/api/references` (CRUD)
- **Database**: SQLite with WAL mode, row factory for dict-like access
- **AI integration**: Calls Ollama's `/api/generate` for Q&A with customizable system prompt in English or Indonesian
- **Bin**: `0.0.0.0:8000` by default

### bible.py (336 lines)

CLI interlinear viewer. Usage: `python3 bible.py John 3:16` or `python3 bible.py Gen 1:1-3`

- Parses book aliases (e.g. "jn" → "John", "kej" → "Gen")
- Fetches original language + English text from SQLite
- Renders colored column output with Strong's, transliteration, original text, gloss, grammar
- Supports OT (Hebrew) and NT (Greek) display modes

### static/index.html (789 lines)

Single-page web application with:

- **Book/chapter/verse selector** — cascading dropdowns populated via API
- **Interlinear display** — table with Strong's, transliteration, original language, gloss, grammar rows
- **Verse navigation** — prev/next links
- **AI Chat sidebar** — ask questions about the passage, with Indonesian language support
- **Commentary sidebar** — Matthew Henry's commentary for the current passage
- **Dark theme** — GitHub-style dark UI
- **Book name aliases** — supports English and Indonesian book names in verse link detection
- **Verse linkification** — auto-links Bible references in AI answers

### static/admin.html (233 lines)

Admin panel for managing curated Q&A references:

- Add/edit/delete references (question + answer + optional verse link)
- Table listing all references with search
- Used by the AI chat as a first-line lookup before querying Ollama

---

## 3. Deployment Architecture

### Option A: Direct Python Server (Not Recommended)

```
Visitor → Python :8000
```

- Simplest but least secure
- No SSL, no caching, no performance optimization
- Must run as root for ports 80/443
- Not production-ready

### Option B: Nginx Reverse Proxy (Recommended for Public IP)

```
Visitor → Port 443 (HTTPS) → Nginx → Python :8000
```

- ✅ SSL via Let's Encrypt (Certbot)
- ✅ Static file caching + compression
- ✅ Python runs as normal user
- ✅ Production-grade security & performance

### Option C: Cloudflare Tunnel (Recommended for CGNAT)

```
Visitor → Cloudflare Edge ← Tunnel (outbound) → Python :8000
```

- ✅ Works without public IP or port forwarding
- ✅ Built-in CDN caching, DDoS protection
- ✅ No SSL certificate management needed
- ✅ Free tier handles everything

### Option D: Cloudflare CDN + Nginx (Best Overall)

```
Visitor → Cloudflare CDN (cached assets) → Nginx → Python :8000
          (only API/uncached requests reach your server)
```

- Combines CDN benefits with local Nginx
- Static files served from Cloudflare edge worldwide
- Your server only handles API/dynamic requests
- Best performance for a global audience

---

## 4. DDNS & Dynamic IP Solution

### The Problem

When your server PC restarts, the ISP may assign a new public IP. Your domain's DNS record still points to the old IP, so visitors can't reach your server.

### The Solution: DDNS (Dynamic DNS)

A DDNS client runs on your server, periodically checking your public IP. When it changes, it calls the DDNS provider's API to update the DNS A record.

```ascii
  ┌─────────────────────────────────────┐
  │  Your Server (PC)                   │
  │                                     │
  │  ┌──────────────┐                  │
  │  │ DDNS Client  │──▶ API call ──────┼──▶ DuckDNS / Cloudflare
  │  │ (runs every  │   "set A record  │     (updates DNS)
  │  │  1-5 min)    │    → 5.6.7.8"    │
  │  └──────────────┘                  │
  │                                     │
  │  Public IP: 5.6.7.8                 │
  └─────────────────────────────────────┘
                      │
                      ▼
          Domain DNS: bible.domain.com
          A record → 5.6.7.8
```

### DDNS Providers

| Provider | Cost | Features |
|---|---|---|
| **DuckDNS** | Free | Simple, dead-simple setup, `yourname.duckdns.org` |
| **Cloudflare** | Free | CDN included, DDoS protection, analytics, any domain |
| **No-IP** | Free (with domain) / Paid | Well-known, paid option for custom domains |

### CGNAT Issue

Some ISPs use Carrier-Grade NAT — you share a public IP and cannot receive incoming connections.

**Check:** Compare `curl -s ifconfig.me` (public IP) with your router's WAN IP or `hostname -I`. If they differ → CGNAT.

**Solution:** Use Cloudflare Tunnel (no open ports needed).

---

## 5. Performance Best Practices

### Nginx Reverse Proxy Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name bible.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/bible.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bible.yourdomain.com/privkey.pem;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    # Proxy to Python server
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;

        # Buffering optimizations
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;

        # Keepalive
        keepalive_timeout 65;
    }

    # Static files (cached aggressively)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # Cache static files
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

### Cloudflare Free Plan Optimizations

- ✅ **Auto Minify** — HTML, CSS, JS automatically minified
- ✅ **Brotli Compression** — better compression ratio than gzip
- ✅ **HTTP/2 + HTTP/3** — multiplexed connections, faster loading
- ✅ **Edge Cache** — static files cached in 330+ data centers worldwide
- ✅ **Always Online** — serves cached content if origin is down
- ✅ **Railgun** — optimizes dynamic content delivery (if using Cloudflare proxy)

### Database Optimizations

- SQLite WAL mode (already configured in `server.py:51`)
- `busy_timeout=5000` prevents lock contention
- Indexes on `book_code, chapter, verse` (primary key)
- Separate tables for English, Hebrew, Greek for query efficiency

### System Resource Tuning

```bash
# /etc/sysctl.conf — TCP optimizations
net.core.somaxconn = 1024
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_congestion_control = bbr
```

---

## 6. Full Deployment Plan (Ubuntu/Debian)

### Prerequisites

- Ubuntu 20.04+ or Debian 11+
- Domain name (e.g. `yourdomain.com` or `duckdns.org`)
- Port 80/443 forwarded to your server PC (or Cloudflare Tunnel)
- Python 3.8+ installed

### Step 1: Install Nginx + Certbot

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Step 2: Configure DDNS

**Option A: DuckDNS (simplest)**

```bash
sudo apt install -y ddclient
# Configure /etc/ddclient.conf with your DuckDNS token
```

Or create a cron job:

```bash
echo "*/5 * * * * curl -s 'https://www.duckdns.org/update?domains=yourdomain&token=XXXXX&ip=' > /dev/null" | crontab -
```

**Option B: Cloudflare DDNS**

```bash
# Install cloudflare-ddns client
pip3 install cloudflare-ddns
```

### Step 3: Set up SSL

```bash
sudo certbot --nginx -d bible.yourdomain.com
```

### Step 4: Create systemd Service for Python Server

```ini
; /etc/systemd/system/bible-server.service
[Unit]
Description=Bible Interlinear Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/Bible_A1
ExecStart=/usr/bin/python3 /path/to/Bible_A1/server.py
Restart=always
RestartSec=5
Environment="OLLAMA_URL=http://127.0.0.1:11434"
Environment="OLLAMA_MODEL=llama3.1:8b"

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bible-server
```

### Step 5: Configure Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/bible
server {
    listen 80;
    server_name bible.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name bible.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/bible.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bible.yourdomain.com/privkey.pem;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/bible /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Step 6: Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b
# Optional: pull Indonesian-capable model
ollama pull llama3.1:8b
```

Ollama runs as a systemd service automatically.

### Step 7: Configure Firewall

```bash
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp       # HTTP
sudo ufw allow 443/tcp      # HTTPS
sudo ufw deny 8000          # Python server (not directly exposed)
sudo ufw enable
```

### Step 8: Set Up Cloudflare (Optional but Recommended)

1. Add your domain to Cloudflare (free plan)
2. Set DNS A record to your public IP (proxied: orange cloud)
3. In Cloudflare dashboard → Speed → Optimization:
   - Enable Auto Minify (HTML, CSS, JS)
   - Enable Brotli compression
   - Enable HTTP/2
4. SSL/TLS → Full (strict)

### Step 9: Testing

```bash
# Test the server locally
curl http://localhost:8000/api/books

# Test via nginx
curl https://bible.yourdomain.com/api/books

# Test the web UI
# Open https://bible.yourdomain.com in a browser

# Test AI chat
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is faith?","lang":"en"}'

# Check systemd status
sudo systemctl status bible-server

# Check Ollama
sudo systemctl status ollama
curl http://localhost:11434/api/tags
```

---

## 7. FAQ

### Q: Do I need a fixed IP?

**No.** DDNS handles dynamic IPs automatically. The DDNS client on your server updates the DNS record whenever your IP changes.

### Q: Do I need a VPN?

**No.** Visitors connect directly to your server's public IP (via DNS). A VPN would add latency and complexity for no benefit.

### Q: Do I need a public IP from my ISP?

**Yes — unless you use Cloudflare Tunnel.** Without a public IP or a tunnel, visitors can't reach your server. Check for CGNAT by comparing `curl -s ifconfig.me` with your router's WAN IP.

### Q: What if my IP changes while someone is using the site?

- DNS changes take 1-5 minutes to propagate (with low TTL like 60-300 seconds)
- Active connections (established TCP) to the **old IP** will drop when the server reboots, not when the IP changes
- Cloudflare Tunnel users: no disruption, because the tunnel is outbound and stays connected regardless of IP changes

### Q: What is Cloudflare Tunnel vs. Cloudflare CDN?

| Feature | Cloudflare CDN (proxy) | Cloudflare Tunnel |
|---|---|---|
| Needs public IP | ✅ Yes | ❌ No |
| Needs open ports | ✅ Yes (80/443) | ❌ No |
| Works with CGNAT | ❌ No | ✅ Yes |
| Caches static files | ✅ Yes | ✅ Yes |
| Setup complexity | Easy | Moderate |

### Q: Which is better for a home server without fixed IP?

**Best:** Cloudflare CDN + Nginx + DDNS (if you have a public IP)
**Alternative:** Cloudflare Tunnel (if you're behind CGNAT or prefer zero open ports)

### Q: How much does all of this cost?

- Domain: $0-12/year (DuckDNS is free, `.com` domains ~$12/year)
- Cloudflare: Free tier sufficient
- SSL certificate: Free (Let's Encrypt)
- Ollama: Free (open source)
- Server: Your existing PC + electricity
- **Total: ~$0-12/year**

### Q: What if the server PC restarts?

1. Systemd auto-starts the Python server
2. Systemd auto-starts Ollama
3. DDNS client auto-updates IP if changed
4. After ~1-5 minutes, everything is accessible again
5. Cloudflare Tunnel reconnects automatically within seconds

---

## Quick Start (Minimal — for testing locally)

```bash
# 1. Clone and navigate
cd /media/azmarpop/DATA/MY_AI/Bible_A1

# 2. Start the server
python3 server.py

# 3. Open browser
# http://localhost:8000

# 4. Or use CLI
python3 bible.py John 3:16
```
