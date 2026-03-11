/**
 * Wavely — Service Worker (Phase 2)
 * ═══════════════════════════════════
 * Offline strategy:
 *  - App shell (HTML/fonts) → Cache first
 *  - API search calls       → Network first, fall back to cache
 *  - Audio stream URLs      → Network only (too large to cache)
 *  - Google Fonts           → Cache first (stable assets)
 */

const CACHE_NAME    = 'wavely-v3';   // bump version to force refresh
const SHELL_ASSETS  = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

// ── INSTALL: cache app shell ─────────────────────────────────────────────────
self.addEventListener('install', event => {
  console.log('[SW] Installing v2…');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())   // activate immediately
  );
});

// ── ACTIVATE: delete old caches ──────────────────────────────────────────────
self.addEventListener('activate', event => {
  console.log('[SW] Activating…');
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => {
          console.log('[SW] Deleting old cache:', k);
          return caches.delete(k);
        })
      ))
      .then(() => self.clients.claim())
  );
});

// ── FETCH: routing ────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET
  if (request.method !== 'GET') return;

  // Audio stream URLs — always network only (too large, expires quickly)
  if (url.pathname.includes('/api/stream/')) {
    event.respondWith(fetch(request));
    return;
  }

  // API search calls — network first, cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstWithCache(request, 'wavely-api-cache'));
    return;
  }

  // Google Fonts — cache first (very stable)
  if (url.hostname.includes('fonts.googleapis.com') ||
      url.hostname.includes('fonts.gstatic.com')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Everything else (app shell) — cache first
  event.respondWith(cacheFirst(request));
});

// ── Strategy: Cache first ─────────────────────────────────────────────────────
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Offline + not cached → friendly page
    return new Response(
      `<!DOCTYPE html>
      <html><head><meta charset="UTF-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <title>Wavely — Offline</title>
      <style>
        body { background:#0d0d14; color:#e8e8f0; font-family:sans-serif;
               display:flex; align-items:center; justify-content:center;
               min-height:100vh; text-align:center; padding:24px; }
        h1 { font-size:32px; margin-bottom:12px; }
        p  { color:#7a7a9a; font-size:15px; max-width:300px; }
      </style></head>
      <body>
        <div>
          <div style="font-size:56px;margin-bottom:16px">🎵</div>
          <h1>You're Offline</h1>
          <p>Connect to the internet to search for music.<br/>
             Your favourites and recently played songs are still available!</p>
        </div>
      </body></html>`,
      { headers: { 'Content-Type': 'text/html' } }
    );
  }
}

// ── Strategy: Network first, cache fallback ───────────────────────────────────
async function networkFirstWithCache(request, cacheName = CACHE_NAME) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;

    return new Response(
      JSON.stringify({ error: 'Offline — could not reach server.', offline: true }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}