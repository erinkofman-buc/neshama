// Neshama Service Worker - Basic offline caching
const CACHE_NAME = 'neshama-v1';
const STATIC_ASSETS = [
  '/',
  '/feed',
  '/about',
  '/faq',
  '/privacy',
  '/app.js',
  '/favicon.svg',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

// Install: cache static assets
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(key) { return key !== CACHE_NAME; })
            .map(function(key) { return caches.delete(key); })
      );
    })
  );
  self.clients.claim();
});

// Fetch: network-first for API/dynamic, cache-first for static
self.addEventListener('fetch', function(event) {
  var url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // API requests: network only, don't cache
  if (url.pathname.startsWith('/api/')) return;

  // Static assets: cache-first
  event.respondWith(
    caches.match(event.request).then(function(cached) {
      if (cached) {
        // Return cache, update in background
        fetch(event.request).then(function(response) {
          if (response.ok) {
            caches.open(CACHE_NAME).then(function(cache) {
              cache.put(event.request, response);
            });
          }
        }).catch(function() {});
        return cached;
      }
      // Not cached: fetch from network
      return fetch(event.request).then(function(response) {
        if (response.ok && url.origin === self.location.origin) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      });
    })
  );
});
