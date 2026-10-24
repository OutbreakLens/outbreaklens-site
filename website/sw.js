/* OutbreakLens service worker (built 2026-10-24). It makes the site installable and keeps the last pages,
   map data and map tiles it loaded, so the app still opens without a signal. To switch it off, replace this
   file with one that calls self.registration.unregister() and deploy. */
const VERSION = 'ol-bd702e99';
const CORE = VERSION + '-core', PAGES = VERSION + '-pages', STATIC = VERSION + '-static';
const DATA = 'ol-data', TILES = 'ol-tiles';
const PRECACHE = ["/offline", "/assets/styles.css?v=7251db53", "/assets/favicon.svg", "/assets/icon-192.png"];
const OPTIONAL = ["/map", "/assets/map.js?v=8f43241e", "/assets/data/map.geojson"];
const TILE_HOSTS = ['tiles.openfreemap.org'];
const STATIC_HOSTS = ['cdnjs.cloudflare.com', 'fonts.googleapis.com', 'fonts.gstatic.com'];
const MAX_TILES = 600, MAX_PAGES = 40;

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CORE)
    .then((c) => c.addAll(PRECACHE).then(() => c.addAll(OPTIONAL).catch(() => null)))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys
      .filter((k) => k.startsWith('ol-') && !k.startsWith(VERSION) && k !== DATA && k !== TILES)
      .map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

function cacheable(res) { return res && res.ok && !res.redirected && (res.type === 'basic' || res.type === 'cors'); }

// Cloudflare Pages serves /map for map.html and redirects /map.html to /map, so a page can sit in the cache
// under either address. A redirected response can't answer a navigation, so it is rebuilt as a plain one.
function clean(res) {
  if (!res || !res.redirected) { return res; }
  return res.blob().then((body) => new Response(body, { status: res.status, statusText: res.statusText, headers: res.headers }));
}
function otherAddress(url) {
  const u = new URL(url);
  if (u.pathname.endsWith('/index.html')) { u.pathname = u.pathname.slice(0, -10); }
  else if (u.pathname.endsWith('.html')) { u.pathname = u.pathname.slice(0, -5); }
  else if (!/\.[a-z0-9]+$/i.test(u.pathname) && !u.pathname.endsWith('/')) { u.pathname += '.html'; }
  else { return null; }
  u.search = '';
  return u.href;
}

function keep(event, promise) { try { event.waitUntil(promise); } catch (e) { /* the event has ended */ } }

async function trim(name, max) {
  const cache = await caches.open(name);
  const keys = await cache.keys();
  for (let i = 0; i < keys.length - max; i++) { await cache.delete(keys[i]); }
}

// Network first: fresh when online, the last copy when not. With a timeout, a slow network falls back to the
// last copy if there is one, otherwise it keeps waiting. Pages with nothing cached get the offline page.
async function networkFirst(event, req, name, timeoutMs, fallbackUrl) {
  const cache = await caches.open(name);
  const network = fetch(req).then((res) => {
    if (cacheable(res)) {
      const copy = res.clone();
      keep(event, cache.put(req, copy).then(() => (name === PAGES ? trim(PAGES, MAX_PAGES) : null)));
    }
    return res;
  });
  network.catch(() => null);
  const lastCopy = async () => {
    const nav = req.mode === 'navigate';
    let hit = await caches.match(req, { ignoreSearch: nav });
    if (!hit && nav) { const alt = otherAddress(req.url); if (alt) { hit = await caches.match(alt, { ignoreSearch: true }); } }
    return clean(hit);
  };
  const offline = async (err) => {
    if (fallbackUrl) { const page = await caches.match(fallbackUrl); if (page) { return clean(page); } }
    throw err;
  };
  if (timeoutMs) {
    const timer = new Promise((resolve) => setTimeout(resolve, timeoutMs, 'timeout'));
    const first = await Promise.race([network.catch(() => 'error'), timer]);
    if (first !== 'timeout' && first !== 'error') { return first; }
    const hit = await lastCopy();
    if (hit) { return hit; }
  }
  try { return await network; } catch (err) {
    const hit = await lastCopy();
    if (hit) { return hit; }
    return offline(err);
  }
}

// Stale while revalidate: answer from the cache at once and refresh it in the background.
async function staleWhileRevalidate(event, req, name, max) {
  const cache = await caches.open(name);
  const hit = await cache.match(req);
  const network = fetch(req).then((res) => {
    if (cacheable(res)) {
      const copy = res.clone();
      keep(event, cache.put(req, copy).then(() => (max ? trim(name, max) : null)));
    }
    return res;
  }).catch(() => null);
  if (hit) { keep(event, network); return hit; }
  const res = await network;
  return res || Response.error();
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || req.headers.has('range')) { return; }
  const url = new URL(req.url);
  if (url.origin === self.location.origin) {
    if (url.pathname === '/sw.js') { return; }
    if (req.mode === 'navigate') {
      if (/\.(csv|zip|pdf|xlsx?)$/i.test(url.pathname)) { return; }
      event.respondWith(networkFirst(event, req, PAGES, 4000, '/offline'));
      return;
    }
    if (/^\/assets\/data\/.+\.(json|geojson)$/.test(url.pathname)) {
      event.respondWith(networkFirst(event, req, DATA, 0, null));
      return;
    }
    if (/\.(css|js|png|svg|ico|jpe?g|webp|woff2?)$/i.test(url.pathname) || url.pathname === '/manifest.webmanifest') {
      event.respondWith(staleWhileRevalidate(event, req, STATIC, 0));
    }
    return;
  }
  if (TILE_HOSTS.includes(url.hostname)) { event.respondWith(staleWhileRevalidate(event, req, TILES, MAX_TILES)); return; }
  if (STATIC_HOSTS.includes(url.hostname)) { event.respondWith(staleWhileRevalidate(event, req, STATIC, 0)); }
});
