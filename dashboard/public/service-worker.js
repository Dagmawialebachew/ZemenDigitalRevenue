const CACHE_VERSION = 'zemen-control-shell-v1'
const APP_SHELL = ['./', './manifest.webmanifest', './icons/zemen-control-192.png', './icons/zemen-control-512.png']

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_VERSION).then(cache => cache.addAll(APP_SHELL)))
  self.skipWaiting()
})

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_VERSION).map(key => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', event => {
  const request = event.request
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) caches.open(CACHE_VERSION).then(cache => cache.put('./', response.clone()))
          return response
        })
        .catch(() => caches.match('./')),
    )
    return
  }

  if (!['script', 'style', 'image', 'font', 'manifest'].includes(request.destination)) return
  event.respondWith(
    caches.match(request).then(cached => {
      const fresh = fetch(request).then(response => {
        if (response.ok) caches.open(CACHE_VERSION).then(cache => cache.put(request, response.clone()))
        return response
      })
      if (cached) {
        event.waitUntil(fresh.catch(() => undefined))
        return cached
      }
      return fresh
    }),
  )
})
