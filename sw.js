const CACHE_NAME = 'misiga-v2026-v2-r20260819-01';
const NAVIGATION_NETWORK_TIMEOUT_MS = 3500;
const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './afiliado.html',
  './afiliado-manifest.json',
  './assets/siga-desktop-icon-128.png',
  './assets/siga-desktop-icon.png',
  './assets/mi-siga-icon-192-2026-v2.png',
  './assets/mi-siga-icon-512-2026-v2.png',
  './assets/mi-siga-icon-180-2026-v2.png',
  './assets/logo-spiqyp-rosario.png',
  './assets/mantenimiento.png',
  './assets/vendor/firebase.js',
  './assets/convenio-77-89-pages/page-01.jpg',
  './assets/convenio-77-89.pdf'
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
        const cached = exactCached || await caches.match('./') || await caches.match('./index.html');
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
