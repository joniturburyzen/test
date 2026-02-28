// SEGARRO 3D - Service Worker
// Primera visita: descarga todo y lo guarda en caché.
// Visitas siguientes: FBX (52MB c/u) salen del disco → carga instantánea.

const CACHE = 'segarro-v6';

// Solo pre-cacheamos el HTML en la instalación.
// Los FBX se cachean automáticamente la primera vez que se descargan (fetch handler).
// Si añadimos los FBX aquí y uno falla, el SW entero no instala.
const FILES = [
  './SEGARROPREMIX.html',
];

// Instalar: cachear archivos esenciales
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(FILES))
  );
  self.skipWaiting();
});

// Activar: borrar cachés viejos
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Cache-first: si está en caché lo sirve, si no lo descarga y lo guarda.
// Esto incluye los FBX de RECURSOS/ y los scripts de CDN (Three.js, FBXLoader).
self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(res => {
        // Solo cachear respuestas válidas (evitar errores y respuestas opacas sin CORS)
        if (!res || res.status !== 200 || res.type === 'opaque' || res.type === 'error') {
          return res;
        }
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return res;
      });
    })
  );
});
