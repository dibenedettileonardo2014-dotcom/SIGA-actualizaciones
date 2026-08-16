const CACHE_NAME = 'siga-v1.4.15-r20260816-03';
const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './afiliado.html',
  './afiliado-manifest.json',
  './assets/siga-app-icon.png',
  './assets/siga-app-icon-192.png',
  './assets/siga-app-icon-512.png',
  './assets/logo-spiqyp-rosario.png',
  './assets/mantenimiento.png',
  './assets/vendor/firebase.js',
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
      fetch(event.request)
        .then(response => {
          if (response.ok) {
            const copy = response.clone();
            event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy)));
          }
          return response;
        })
        .catch(() => caches.match(event.request).then(cached => cached || caches.match('./')))
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
