const CACHE_NAME = 'misiga-v2026-v2-r20260819-03-hf2';
const NAVIGATION_NETWORK_TIMEOUT_MS = 3500;
const APP_SHELL = [
  './afiliado.html',
  './afiliado-manifest.json',
  './assets/mi-siga-icon-192-2026-v2.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const sameOrigin = event.request.url.startsWith(self.location.origin);
  if (sameOrigin && event.request.mode === 'navigate') {
    event.respondWith(
      caches.match(event.request).then(async exactCached => {
        // No devolver una navegación cacheada antes de intentar la red: así
        // una instalación anterior recibe la página nueva y su service worker.
        const cached = await caches.match('./afiliado.html');
        const network = fetch(event.request).then(response => {
          if (response.ok) {
            const copy = response.clone();
            event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy)));
          }
          return response;
        }).catch(error => {
          if (cached) return cached;
          throw error;
        });
        if (!cached) return network;
        const timeout = new Promise(resolve => setTimeout(() => resolve(cached), NAVIGATION_NETWORK_TIMEOUT_MS));
        return Promise.race([network, timeout]);
      })
    );
    return;
  }
  const staticAsset = sameOrigin && ['image', 'font'].includes(event.request.destination)
    || sameOrigin && /\.(?:pdf|ico)$/i.test(new URL(event.request.url).pathname);
  if (staticAsset) {
    event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
      if (!response.ok) return response;
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy)).catch(() => {});
      return response;
    })));
    return;
  }
  event.respondWith(fetch(event.request).then(response => {
    if (sameOrigin && response.ok) {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy)).catch(() => {});
    }
    return response;
  }).catch(() => caches.match(event.request).then(response => response || (event.request.mode === 'navigate' ? caches.match('./') : Response.error()))));
});
