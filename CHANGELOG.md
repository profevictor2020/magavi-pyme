# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Fase 1 — Estructura del proyecto + Docker + PostgreSQL

- Backend Django + DRF: proyecto `config`, apps de dominio vacías
  (`core`, `accounts`, `companies`, `catalog`, `sales`, `purchases`,
  `inventory`, `cashbox`, `documents`, `assistant`, `audit`), endpoint
  `GET /api/health/`, configuración por variables de entorno, PostgreSQL
  como único motor de base de datos.
- Frontend React + Vite + TypeScript: página placeholder, lint (oxlint) y
  build verificados.
- `docker-compose.yml` (postgres, backend, frontend) y `.env.example`.
- CI (GitHub Actions): job backend (`ruff` + `pytest` contra Postgres
  real) y job frontend (`lint` + `build`).
- Verificado localmente: migraciones aplicadas, test de health en verde,
  servidor real respondiendo a `curl`, build de frontend sin errores.
- Sin modelos de negocio, autenticación ni UI real todavía (eso es Fase
  2 en adelante).

### Fase 0 — Arquitectura y planificación

- Documentación inicial de arquitectura: `docs/PRODUCT.md`,
  `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/SECURITY.md`,
  `docs/ROADMAP.md`, `docs/TESTING.md`, `docs/DECISIONS.md`.
- `README.md` con visión general del proyecto y estado actual.
- Definición de 13 fases (0–12) de desarrollo incremental, cada una con
  objetivo, alcance, pruebas y criterio de aceptación.
- Sin código de aplicación todavía — pendiente de aprobación de Fase 0
  para iniciar Fase 1 (estructura del proyecto + Docker + PostgreSQL).
