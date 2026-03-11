# 🎵 Wavely — Free Music Streaming PWA

> Stream any song for free. No ads. No subscription. Installable on any device.

A full-stack music streaming Progressive Web App built with **FastAPI** (Python) + **Vanilla HTML/CSS/JS** — powered by the YouTube Data API and yt-dlp.

🌐 **Live Demo:** [wavely-music.vercel.app](https://wavely-music.vercel.app)

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔍 **Search** | Search millions of songs via YouTube Data API with autocomplete |
| ▶ **Audio Streaming** | Audio-only streaming via yt-dlp — no video buffering |
| 🎤 **Synced Lyrics** | Karaoke-style line-by-line lyrics via LRClib (free, no key needed) |
| 📋 **Queue System** | Add songs to queue, reorder, play next |
| 🔀 **Shuffle & Loop** | Full playback controls |
| ❤️ **Favourites** | Save favourite songs (localStorage) |
| 🕐 **Recently Played** | Auto-tracks listening history |
| 🌐 **Discover** | Trending songs by genre with horizontal scroll rows |
| 📱 **PWA** | Installable on Android & iOS — works like a native app |
| 🔒 **Lock Screen Controls** | Media Session API — control playback from notification shade |
| 💾 **Offline Mode** | Service Worker caches app shell for offline use |
| 🌙 **Dark / Light Mode** | Theme toggle with localStorage persistence |
| 🔍 **Autocomplete** | Live YouTube suggestions + recent searches dropdown |
| ➕ **Pagination** | Load more results without scroll reset |

---

## 🗂 Project Structure

```
music-streaming-app/
├── backend/
│   ├── main.py            # FastAPI app — all API routes
│   ├── requirements.txt   # Python dependencies
│   ├── .env               # Your API key (never commit this)
│   └── render.yaml        # Render deployment config
│
├── frontend/
│   ├── index.html         # Single-page app (UI + all JS)
│   ├── manifest.json      # PWA manifest
│   ├── sw.js              # Service Worker (offline + caching)
│   ├── vercel.json        # Vercel deployment config
│   └── icons/
│       ├── icon-192.png
│       └── icon-512.png
│
├── .gitignore
└── README.md
```

---

## 🔑 Prerequisites

- Python 3.10+
- A free **YouTube Data API v3** key

### Getting a YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project → **APIs & Services** → **Enable APIs**
3. Search **YouTube Data API v3** → Enable
4. **Credentials** → **Create Credentials** → **API Key**
5. Copy the key

> **Free quota:** 10,000 units/day (~100 searches).

---

## 🖥 Running Locally

### 1 — Backend Setup

```bash
cd music-streaming-app/backend

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo YOUTUBE_API_KEY=your_key_here > .env
```

### 2 — Start Backend

```bash
uvicorn main:app --reload --port 8000
```

Visit [http://localhost:8000](http://localhost:8000) → `{"status":"ok"}`  
API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3 — Start Frontend

```bash
cd music-streaming-app/frontend
python -m http.server 3000
```

Open [http://localhost:3000](http://localhost:3000) 🎵

---

## 🌐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/api/search?q={query}&max_results=12&page_token={token}` | Search songs |
| `GET` | `/api/suggestions?q={query}` | Autocomplete suggestions |
| `GET` | `/api/song/{video_id}` | Song metadata |
| `GET` | `/api/stream/{video_id}` | Audio stream URL |
| `GET` | `/api/lyrics?title={title}&artist={artist}` | Synced/plain lyrics |

---

## 🚀 Deployment

> ⚠️ **Known Limitation:** YouTube blocks yt-dlp on cloud server IPs (Render, Railway, etc.).
> The app works fully when the backend runs **locally** or on a **residential/VPS IP**.
> For a live demo, expose the local backend via [ngrok](https://ngrok.com).

### Option 1 — Local Backend + ngrok (Recommended for demo)

```bash
# Terminal 1 — start backend
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2 — expose publicly
ngrok http 8000
```

Update `BACKEND_URL` in `frontend/index.html` with your ngrok URL.

### Option 2 — Frontend on Vercel (Always live)

1. Push repo to GitHub
2. [vercel.com](https://vercel.com) → **New Project** → import repo
3. **Root Directory** → `frontend` | **Framework** → `Other`
4. Deploy

---

## 📱 Install as Mobile App (PWA)

**Android:** Chrome → ⋮ menu → **Add to Home Screen**  
**iOS:** Safari → Share → **Add to Home Screen**

---

## 🛠 Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) — Python web framework
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube audio extraction
- [httpx](https://www.python-httpx.org/) — Async HTTP client
- YouTube Data API v3 — Search & metadata
- [LRClib](https://lrclib.net/) — Free synced lyrics API (no key needed)

**Frontend**
- Vanilla HTML / CSS / JavaScript — no frameworks
- Syne + DM Sans (Google Fonts)
- Web Audio API + Media Session API
- Service Worker (PWA + offline support)

---

## 🛠 Troubleshooting

| Issue | Fix |
|---|---|
| "Requested format is not available" | YouTube IP block on cloud — run backend locally |
| "Sign in to confirm you're not a bot" | Add `cookies.txt` from browser — see [yt-dlp docs](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp) |
| CORS errors | Check `BACKEND_URL` in `index.html` matches your backend URL |
| Phone can't connect locally | Use `--host 0.0.0.0`, same WiFi, use local IP not localhost |

---

## 📄 License

MIT — free for personal and commercial use.

---

Built with ❤️ by [Nihal Vernekar](https://linkedin.com/in/nihal-vernekar-a4b31916b) · [GitHub](https://github.com/Nihal2999)