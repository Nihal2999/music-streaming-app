"""
🎵 Music Streaming App — FastAPI Backend
========================================
Uses YouTube Data API for search/metadata and yt-dlp for audio streaming.
"""

import os
import shutil
import logging
from typing import Optional

import httpx
import yt_dlp
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from dotenv import load_dotenv

# ── Load environment variables from .env file ──────────────────────────────────
load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

# ── Logger ─────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Copy cookies to writable /tmp on Render (secret files are read-only) ───────
_RENDER_COOKIES = "/etc/secrets/cookies.txt"
_TMP_COOKIES    = "/tmp/cookies.txt"
_LOCAL_COOKIES  = "cookies.txt"

if os.path.exists(_RENDER_COOKIES):
    shutil.copy(_RENDER_COOKIES, _TMP_COOKIES)
    COOKIES_PATH = _TMP_COOKIES
elif os.getenv("COOKIES_CONTENT"):
    with open(_TMP_COOKIES, "w") as f:
        f.write(os.getenv("COOKIES_CONTENT"))
    COOKIES_PATH = _TMP_COOKIES
    logger.info("Cookies written from environment variable")
elif os.path.exists(_LOCAL_COOKIES):
    COOKIES_PATH = _LOCAL_COOKIES
else:
    COOKIES_PATH = None

# ── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Music Streaming API",
    description="Backend API for a free music streaming web app powered by YouTube.",
    version="1.0.0",
)

# ── CORS Middleware ────────────────────────────────────────────────────────────
# This allows the frontend (running on a different domain/port) to talk to us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # In production, restrict to your Vercel frontend URL
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# HELPER: Build a common YouTube song result dict
# ──────────────────────────────────────────────────────────────────────────────
def build_song(video_id: str, title: str, channel: str, thumbnail: str, duration: str = ""):
    """Return a standardized song dictionary."""
    return {
        "id": video_id,
        "title": title,
        "artist": channel,
        "thumbnail": thumbnail,
        "duration": duration,
        "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
    }


# ──────────────────────────────────────────────────────────────────────────────
# HELPER: Convert ISO 8601 duration (PT4M13S) → "4:13"
# ──────────────────────────────────────────────────────────────────────────────
def parse_duration(iso: str) -> str:
    """Convert YouTube ISO 8601 duration string to MM:SS format."""
    import re
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not match:
        return "0:00"
    hours = int(match.group(1) or 0)
    mins  = int(match.group(2) or 0)
    secs  = int(match.group(3) or 0)
    if hours:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


# ──────────────────────────────────────────────────────────────────────────────
# ROUTE: Health check
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    """Simple health-check endpoint."""
    return {"status": "ok", "message": "Music Streaming API is running 🎵"}


# ──────────────────────────────────────────────────────────────────────────────
# ROUTE: Search songs
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/search", tags=["Songs"])
async def search_songs(
    q: str = Query(..., description="Search query, e.g. 'Bohemian Rhapsody'"),
    max_results: int = Query(12, ge=1, le=25, description="Number of results"),
    page_token: Optional[str] = Query(None, description="YouTube nextPageToken for pagination"),
):
    """
    Search for songs using the YouTube Data API.

    Returns a list of song objects with id, title, artist, thumbnail, duration.
    """
    if not YOUTUBE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="YOUTUBE_API_KEY is not set. Please add it to your .env file.",
        )

    # Step 1: Search for videos matching the query
    search_params = {
        "part": "snippet",
        "q": f"{q} official audio",   # bias toward official audio results
        "type": "video",
        "videoCategoryId": "10",       # Category 10 = Music
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY,
    }

    # Add pagination token if provided
    if page_token:
        search_params["pageToken"] = page_token

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(YOUTUBE_SEARCH_URL, params=search_params)

    if resp.status_code != 200:
        logger.error("YouTube search error: %s", resp.text)
        raise HTTPException(status_code=502, detail="YouTube API search failed.")

    resp_json        = resp.json()
    items            = resp_json.get("items", [])
    next_page_token  = resp_json.get("nextPageToken")
    if not items:
        return {"results": [], "next_page_token": None}

    # Step 2: Fetch durations for found videos in one batch call
    video_ids = ",".join(item["id"]["videoId"] for item in items)
    details_params = {
        "part": "contentDetails",
        "id": video_ids,
        "key": YOUTUBE_API_KEY,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        details_resp = await client.get(YOUTUBE_VIDEOS_URL, params=details_params)

    duration_map: dict[str, str] = {}
    if details_resp.status_code == 200:
        for vid in details_resp.json().get("items", []):
            raw = vid.get("contentDetails", {}).get("duration", "")
            duration_map[vid["id"]] = parse_duration(raw)

    # Step 3: Build results list
    results = []
    for item in items:
        vid_id    = item["id"]["videoId"]
        snippet   = item["snippet"]
        thumbnail = (
            snippet.get("thumbnails", {})
            .get("high", {})
            .get("url", "")
            or snippet.get("thumbnails", {}).get("default", {}).get("url", "")
        )
        results.append(
            build_song(
                video_id  = vid_id,
                title     = snippet.get("title", "Unknown Title"),
                channel   = snippet.get("channelTitle", "Unknown Artist"),
                thumbnail = thumbnail,
                duration  = duration_map.get(vid_id, ""),
            )
        )

    logger.info("Search '%s' (token=%s) returned %d results.", q, page_token, len(results))
    return {"results": results, "next_page_token": next_page_token}



# ──────────────────────────────────────────────────────────────────────────────
# ROUTE: Search suggestions (proxies YouTube autocomplete)
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/suggestions", tags=["Songs"])
async def get_suggestions(q: str = Query(..., description="Partial search query")):
    """
    Returns autocomplete suggestions for a query by proxying
    YouTube's suggestion API (fixes CORS — browser can't call it directly).
    Returns up to 8 suggestion strings.
    """
    if not q.strip():
        return {"suggestions": []}
    try:
        url = "https://suggestqueries.google.com/complete/search"
        params = {
            "client": "youtube",
            "ds":     "yt",
            "q":      q,
            "hl":     "en",
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params)

        # Response is JSONP: window.google.ac.h([...])
        # Parse out the JSON array inside
        text = resp.text
        start = text.index("[")
        # The suggestions are in the second element: [query, [[s1,0],[s2,0],...]]
        import json
        data        = json.loads(text[start : text.rindex("]") + 1])
        raw_list    = data[1] if len(data) > 1 else []
        suggestions = [item[0] for item in raw_list if isinstance(item, list)][:8]
        return {"suggestions": suggestions}
    except Exception as e:
        logger.warning("Suggestions error: %s", e)
        return {"suggestions": []}


# ──────────────────────────────────────────────────────────────────────────────
# ROUTE: Lyrics (via LRClib — free, no API key needed)
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/lyrics", tags=["Songs"])
async def get_lyrics(
    title:  str = Query(..., description="Song title"),
    artist: str = Query(..., description="Artist / channel name"),
):
    """
    Fetch synced (LRC) or plain lyrics from LRClib.net.
    Returns: { synced: [{time, text}], plain: "...", found: bool }
    """
    import re

    def clean(s: str) -> str:
        """Strip common YouTube title noise for better matching."""
        s = re.sub(r'\(.*?\)|\[.*?\]', '', s)           # remove (Official Video) etc.
        s = re.sub(r'ft\.?\s+\S+', '', s, flags=re.I)    # remove ft. artist
        s = re.sub(r'[^\w\s]', ' ', s)
        return s.strip()

    def parse_lrc(lrc: str):
        """Parse LRC format into list of {time (seconds), text}."""
        lines = []
        for line in lrc.splitlines():
            m = re.match(r'\[(\d+):(\d+\.?\d*)\](.*)', line)
            if m:
                mins, secs, text = m.groups()
                t = int(mins) * 60 + float(secs)
                if text.strip():
                    lines.append({"time": round(t, 2), "text": text.strip()})
        return lines

    base_url = "https://lrclib.net/api"
    headers  = {"User-Agent": "Wavely/1.0 (music streaming app)"}
    queries  = [
        {"track_name": clean(title), "artist_name": clean(artist)},
        {"track_name": clean(title), "artist_name": ""},
        {"q": f"{clean(artist)} {clean(title)}"},
    ]

    async with httpx.AsyncClient(timeout=8.0) as client:
        for params in queries:
            try:
                endpoint = f"{base_url}/search" if "q" in params else f"{base_url}/search"
                resp = await client.get(endpoint, params=params, headers=headers)
                if resp.status_code != 200:
                    continue
                results = resp.json()
                if not results:
                    continue

                # Pick best result — prefer one with synced lyrics
                best = next((r for r in results if r.get("syncedLyrics")), None)
                if not best:
                    best = next((r for r in results if r.get("plainLyrics")), None)
                if not best:
                    continue

                synced_raw = best.get("syncedLyrics", "")
                plain      = best.get("plainLyrics", "")
                synced     = parse_lrc(synced_raw) if synced_raw else []

                logger.info("Lyrics found for '%s' by '%s' (synced=%s)", title, artist, bool(synced))
                return {
                    "found":  True,
                    "synced": synced,
                    "plain":  plain,
                    "title":  best.get("trackName", title),
                    "artist": best.get("artistName", artist),
                }
            except Exception as e:
                logger.warning("LRClib query error: %s", e)
                continue

    return {"found": False, "synced": [], "plain": "", "title": title, "artist": artist}

# ──────────────────────────────────────────────────────────────────────────────
# ROUTE: Get song metadata by video ID
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/song/{video_id}", tags=["Songs"])
async def get_song_metadata(video_id: str):
    """
    Fetch detailed metadata for a single YouTube video/song.
    """
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=500, detail="YOUTUBE_API_KEY is not set.")

    params = {
        "part": "snippet,contentDetails,statistics",
        "id": video_id,
        "key": YOUTUBE_API_KEY,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(YOUTUBE_VIDEOS_URL, params=params)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="YouTube API request failed.")

    items = resp.json().get("items", [])
    if not items:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found.")

    item     = items[0]
    snippet  = item["snippet"]
    details  = item.get("contentDetails", {})
    stats    = item.get("statistics", {})
    thumbnail = (
        snippet.get("thumbnails", {}).get("maxres", {}).get("url")
        or snippet.get("thumbnails", {}).get("high", {}).get("url", "")
    )

    return {
        "id":           video_id,
        "title":        snippet.get("title", ""),
        "artist":       snippet.get("channelTitle", ""),
        "description":  snippet.get("description", "")[:300],
        "thumbnail":    thumbnail,
        "published_at": snippet.get("publishedAt", ""),
        "duration":     parse_duration(details.get("duration", "")),
        "view_count":   stats.get("viewCount", "0"),
        "like_count":   stats.get("likeCount", "0"),
        "youtube_url":  f"https://www.youtube.com/watch?v={video_id}",
    }


# ──────────────────────────────────────────────────────────────────────────────
# ROUTE: Get audio stream URL (via yt-dlp)
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/stream/{video_id}", tags=["Streaming"])
async def get_stream_url(video_id: str):
    """
    Extract a direct audio stream URL for the given YouTube video using yt-dlp.

    The client can then play this URL directly in an <audio> element.
    Note: These URLs expire after a few hours — always fetch fresh before playing.
    """
    ydl_opts = {
        "format": "140/251/250/249/18/22/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "cookiefile": COOKIES_PATH,
    }

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        stream_url = info.get("url")
        if not stream_url:
            raise ValueError("No stream URL found in yt-dlp response.")

        logger.info("Stream URL extracted for video: %s", video_id)
        return {
            "video_id":   video_id,
            "stream_url": stream_url,
            "ext":        info.get("ext", ""),
            "title":      info.get("title", ""),
        }

    except yt_dlp.utils.DownloadError as e:
        logger.warning("yt-dlp DownloadError for %s: %s", video_id, e)
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract stream for this video. It may be restricted. Error: {str(e)[:200]}",
        )
    except Exception as e:
        logger.error("Unexpected error for %s: %s", video_id, e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)[:200]}")


# ──────────────────────────────────────────────────────────────────────────────
# ROUTE: Proxy audio stream (fixes mobile playback)
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/audio/{video_id}", tags=["Streaming"])
async def proxy_audio(video_id: str, request: Request):
    """
    Proxy the audio stream through the backend.
    This fixes mobile browsers (Android/iOS) that block direct YouTube CDN URLs
    due to CORS / origin restrictions.

    Supports HTTP Range requests so the browser can seek in the audio.
    """
    ydl_opts = {
        "format": "140/251/250/249/18/22/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "cookiefile": COOKIES_PATH,
    }

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Handle nested requested_formats
        stream_url = info.get("url")
        if not stream_url and info.get("requested_formats"):
            stream_url = info["requested_formats"][0].get("url")

        if not stream_url:
            raise ValueError("No stream URL found.")

        ext      = info.get("ext", "mp4")
        filesize = info.get("filesize") or info.get("filesize_approx")

        # Forward Range header from client (for seeking)
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
            "Referer":    "https://www.youtube.com/",
            "Origin":     "https://www.youtube.com",
        }

        range_header = request.headers.get("range")
        if range_header:
            headers["Range"] = range_header

        # Determine content type
        content_type = "audio/mp4"
        if ext == "webm": content_type = "audio/webm"
        elif ext == "mp3": content_type = "audio/mpeg"
        elif ext == "m4a": content_type = "audio/mp4"

        # Stream bytes from YouTube CDN → client
        async def stream_audio():
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                async with client.stream("GET", stream_url, headers=headers) as resp:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        yield chunk

        response_headers = {
            "Content-Type":        content_type,
            "Accept-Ranges":       "bytes",
            "Cache-Control":       "no-cache",
            "Access-Control-Allow-Origin": "*",
        }
        if filesize:
            response_headers["Content-Length"] = str(filesize)

        status_code = 206 if range_header else 200
        return StreamingResponse(
            stream_audio(),
            status_code=status_code,
            headers=response_headers,
            media_type=content_type,
        )

    except Exception as e:
        logger.error("Proxy audio error for %s: %s", video_id, e)
        raise HTTPException(status_code=500, detail=f"Could not proxy audio: {str(e)[:200]}")