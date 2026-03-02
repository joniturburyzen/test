// Service Worker — Scotland Guide
const CACHE = 'escocia-v1';
const SHELL = './ezcociapastexreview.html';

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.add(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  clients.claim();
});

// Network-first: intenta la red, si falla sirve la caché (funciona offline)
self.addEventListener('fetch', e => {
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(SHELL))
    );
  }
});
