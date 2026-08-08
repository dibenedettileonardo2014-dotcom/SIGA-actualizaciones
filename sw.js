const CACHE_NAME = 'siga-v1.2.18';
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

  event.respondWith(fetch(event.request).then(response => {
    if (event.request.url.startsWith(self.location.origin)) {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
    }
    return response;
  }).catch(() => caches.match(event.request).then(response => {
    if (response) return response;
    return event.request.mode === 'navigate' ? caches.match('./') : Response.error();
  })));
});
