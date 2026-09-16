/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // e2e/ son specs de Playwright (npm run test:e2e), no de Vitest —
    // sin esto, vitest intenta correrlos en jsdom y fallan.
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
