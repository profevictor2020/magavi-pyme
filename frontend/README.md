# MAGAVI — Frontend

React + Vite + TypeScript, PWA mobile-first. Ver documentación del
proyecto en `../docs/` y el estado general en `../README.md`.

## Desarrollo local

```
npm install
npm run dev
```

Por defecto apunta al backend en `http://localhost:8000/api`. Para
apuntar a otro backend (p. ej. otro puerto en desarrollo), definir
`VITE_API_BASE_URL` antes de levantar el dev server.

## Scripts

- `npm run dev` — servidor de desarrollo.
- `npm run build` — build de producción (`tsc -b && vite build`).
- `npm run lint` — lint con oxlint.
- `npm run test` — tests unitarios/de componentes (Vitest + Testing Library).
- `npm run test:e2e` — guion de demo completo end-to-end (Playwright,
  viewport móvil, ver `e2e/` y `docs/ROADMAP.md` Fase 12). A diferencia
  de los demás scripts, necesita el stack completo real ya arriba
  (backend + worker + Redis + un LLM en `LLM_OLLAMA_BASE_URL`) — no lo
  levanta por sí mismo. En CI corre en su propio job (`e2e` en
  `.github/workflows/ci.yml`) contra `docker-compose.yml` +
  `docker-compose.e2e.yml` (que agrega un LLM de prueba determinístico,
  `backend/scripts/e2e_fake_llm.py`, para no depender de GPU ni red
  externa). Para correrlo a mano contra un stack ya levantado:
  `npx playwright install --with-deps chromium && npm run test:e2e`.
- `npm run preview` — sirve el build de producción localmente.

## Estructura

- `src/api/` — cliente HTTP (`client.ts`, con reintento automático de
  refresh de token JWT y manejo de errores), tipos (`types.ts`, espejo
  de los serializers del backend) y funciones por recurso
  (`endpoints.ts`). Todo endpoint de negocio recibe la empresa activa
  como parámetro explícito (`companyId`), no implícito vía
  `localStorage`, para evitar una condición de carrera entre efectos de
  React (ver `docs/DECISIONS.md` ADR-012).
- `src/context/` — `AuthContext` (sesión) y `CompanyContext` (empresa
  activa, lista de empresas del usuario).
- `src/components/` — layout de la app (barra superior + navegación
  inferior), guardas de ruta (`RequireAuth`/`RequireCompany`), y piezas
  compartidas de UI (`ResultView` para renderizar el resultado de un
  intent/documento confirmado, `ErrorBanner`, `Spinner`).
- `src/pages/` — una pantalla por ruta: `LoginPage`, `RegisterPage`,
  `CompanyPage` (elegir/crear empresa), `ChatPage` (pantalla principal:
  conversación con el asistente, con tarjetas de confirmar/cancelar para
  cada propuesta), `ProductsPage`, `SalesPage`, `PurchasesPage`,
  `CashboxPage` (dashboard), `DocumentsPage`/`DocumentDetailPage`
  (subir foto, revisar extracción OCR, corregir y confirmar).
- `public/manifest.webmanifest`, `public/sw.js`, `public/icons/` — PWA:
  manifest instalable y Service Worker que solo cachea el "shell" de la
  app (nunca `/api/` ni `/media/`, ver ADR-012).

## PWA

La app es instalable (manifest + Service Worker). El Service Worker
(`public/sw.js`) solo se registra en producción (`npm run build` +
servir el `dist/`) — en `npm run dev` se omite a propósito para no
interferir con el hot-reload de Vite.
