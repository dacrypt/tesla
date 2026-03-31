// tesla-cli Service Worker — minimal offline shell
const CACHE = 'tesla-cli-v1';
const SHELL = ['/'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
});

self.addEventListener('fetch', e => {
  // API requests: network only
  if (e.request.url.includes('/api/')) return;
  // Shell: cache-first, fall back to network
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
