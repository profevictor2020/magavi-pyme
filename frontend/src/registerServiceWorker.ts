/** Solo se registra en producción: en dev interferiría con el HMR de
 * Vite al cachear módulos que cambian todo el tiempo. */
export function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return

  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // La app funciona igual sin Service Worker; solo se pierde la
      // instalabilidad/cache de shell, no es un error fatal.
    })
  })
}
