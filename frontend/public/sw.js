// Service Worker de MAGAVI — solo cachea el "shell" de la app para que
// sea instalable y cargue rápido en visitas repetidas (ver
// docs/ARCHITECTURE.md #3.1 y docs/ROADMAP.md Fase 10: "No construir
// soporte offline completo... no cache de datos de negocio sensibles
// por defecto").
//
// Nunca intercepta /api/ ni /media/ (imágenes de documentos subidos):
// esas peticiones siempre van directo a la red, sin caché, para no
// servir datos de negocio desactualizados ni guardar información
// potencialmente sensible (boletas/facturas) donde no corresponde.

const CACHE_NAME = 'magavi-shell-v1'

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

function isApiRequest(url) {
  return url.pathname.startsWith('/api/') || url.pathname.startsWith('/media/')
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  if (event.request.method !== 'GET' || url.origin !== self.location.origin || isApiRequest(url)) {
    return
  }

  // Stale-while-revalidate: sirve desde caché al instante si existe,
  // y en paralelo actualiza la caché con la respuesta de red — así el
  // shell (HTML/JS/CSS con nombre hasheado por build) se cachea solo,
  // sin que este archivo necesite conocer los nombres de antemano.
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(event.request).then((cached) => {
        const network = fetch(event.request)
          .then((response) => {
            if (response.ok) cache.put(event.request, response.clone())
            return response
          })
          .catch(() => cached)
        return cached || network
      }),
    ),
  )
})
