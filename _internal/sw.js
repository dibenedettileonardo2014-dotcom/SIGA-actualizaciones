const CACHE_NAME = 'siga-v1.2.24';
const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './afiliado.html',
  './afiliado-manifest.json',
  './assets/siga-app-icon.png',
  './assets/convenio-77-89.pdf'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
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
  const staticAsset = sameOrigin && ['image', 'font'].includes(event.request.destination)
    || sameOrigin && /\.(?:pdf|ico)$/i.test(new URL(event.request.url).pathname);
  if (staticAsset) {
    event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
      return response;
    })));
    return;
  }
  event.respondWith(fetch(event.request).then(response => {
    if (sameOrigin) {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
    }
    return response;
  }).catch(() => caches.match(event.request).then(response => response || (event.request.mode === 'navigate' ? caches.match('./') : Response.error()))));
});
