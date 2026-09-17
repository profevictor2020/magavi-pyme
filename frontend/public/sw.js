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

// Navegación (el HTML de entrada) o el propio index.html: nunca hay que
// servir esto desde caché si hay red disponible. Bug real encontrado en
// vivo: con stale-while-revalidate para TODO (incluido el HTML), después
// de cada despliegue el navegador seguía mostrando la versión anterior
// de la app — un fix ya desplegado en el servidor no se veía hasta la
// carga SIGUIENTE, porque esta carga servía el HTML viejo (que apunta a
// los archivos JS/CSS de la build anterior) instantáneo desde caché, sin
// esperar la red.
function isNavigationRequest(request, url) {
  return request.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('.html')
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  if (event.request.method !== 'GET' || url.origin !== self.location.origin || isApiRequest(url)) {
    return
  }

  if (isNavigationRequest(event.request, url)) {
    // Network-first: intenta la red siempre primero, y solo cae a la
    // caché si no hay conexión — así una build nueva se ve de inmediato
    // en la próxima carga, no una después.
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, response.clone()))
          }
          return response
        })
        .catch(() => caches.open(CACHE_NAME).then((cache) => cache.match(event.request))),
    )
    return
  }

  // Assets con nombre hasheado por el build (JS/CSS/imágenes): un
  // archivo nuevo siempre tiene un nombre distinto, así que cachearlos
  // agresivamente es seguro — stale-while-revalidate sigue siendo
  // correcto acá (sirve al instante, actualiza la caché en paralelo).
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
