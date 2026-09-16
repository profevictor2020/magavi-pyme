import { defineConfig, devices } from '@playwright/test'

// Reservado para el guion de demo completo (ver docs/ROADMAP.md Fase 12
// y docs/TESTING.md #2 — "no se usa para cubrir lógica de negocio, eso
// ya está en unit/integration"). Corre contra el stack completo real
// (docker-compose.yml + docker-compose.e2e.yml), nunca contra mocks —
// por eso no hay un `webServer` acá: quien invoca `playwright test`
// (el job `e2e` de CI, o un desarrollador local) es responsable de
// tener el stack ya arriba.
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  // En CI: salida de consola legible (list) + un reporte HTML que el
  // job `e2e` sube como artefacto solo si algo falla (ver ci.yml).
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'html',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // Permite apuntar a un binario de Chromium ya instalado (p. ej. en
    // un entorno sandboxeado sin acceso de red para `playwright install`)
    // sin tener que hardcodear una ruta específica del entorno acá.
    launchOptions: process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {},
  },
  projects: [
    {
      // Viewport móvil real (ver docs/TESTING.md): el guion de demo se
      // prueba como se usaría en la realidad, con el pulgar en un
      // celular Android de gama media, no en un navegador de escritorio.
      name: 'chromium-mobile',
      use: { ...devices['Pixel 7'] },
    },
  ],
})
