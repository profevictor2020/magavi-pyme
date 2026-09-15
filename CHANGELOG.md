# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Fase 3 — Productos + inventario

- Modelo `Product` (`catalog`), con scope de empresa
  (`CompanyScopedManager`), CRUD vía API sin borrado físico (`DELETE`
  devuelve 405; se desactiva con `is_active`), SKU único por empresa
  (nullable), stock cacheado (`current_stock`) y umbral de stock bajo
  configurable por producto (`low_stock_threshold`).
- Modelo `InventoryMovement` (`inventory`) como historial auditable de
  cada cambio de stock (delta con signo, saldo resultante, motivo, quién
  y cuándo).
- Tool Layer `ajustar_inventario` (`inventory/services.py`): único punto
  de escritura de movimientos de inventario, transaccional con
  `select_for_update()` para evitar condiciones de carrera, y que
  rechaza explícitamente dejar el stock en negativo (ver
  `docs/DECISIONS.md` ADR-009). Pensado para ser reutilizado sin cambios
  por `crear_venta`/`registrar_compra` (Fases 4/5) y por el asistente
  (Fase 8).
- Endpoints: `GET/POST /api/products/` (con `initial_stock` opcional al
  crear y filtro `?low_stock=true`), `GET/PATCH/PUT
  /api/products/<id>/`, `POST /api/products/<id>/adjust-stock/`.
- 20 tests nuevos (42 en total): unit del Tool Layer (ajustes positivos y
  negativos, rechazo de stock negativo, rechazo de producto de otra
  empresa) e integración de la API (CRUD, SKU único por empresa, stock
  bajo, y el gate obligatorio de aislamiento multiempresa aplicado a
  productos).
- Verificado localmente: migraciones desde cero, suite completa en
  verde, y un recorrido manual por HTTP (crear producto con stock
  inicial, ajustar stock, ver stock bajo, e intentos inválidos
  correctamente rechazados).
- Sin ventas, compras ni asistente todavía (eso es Fase 4 en adelante).

### Fase 2 — Usuarios + empresas + autenticación + multi-tenancy

- Modelo de usuario custom (`accounts.User`, login por email) con
  Argon2 como hasher de contraseña.
- Autenticación JWT (`djangorestframework-simplejwt`): registro
  (`POST /api/auth/register/`), login (`/login/`), refresh
  (`/refresh/`), logout con blacklist de refresh token (`/logout/`),
  usuario actual (`/me/`).
- Modelos `Company`, `CompanyUser` (con rol owner/admin/staff),
  `Module`, `CompanyModule`.
- `POST/GET /api/companies/` ("mis empresas" / crear empresa, el
  creador queda como owner) y `GET /api/companies/<id>/`.
- Mecanismo de aislamiento multiempresa: `core/tenancy.py`
  (`get_current_company`, resuelve la empresa activa vía header
  `X-Company-Id` validando membresía) y `core/managers.py`
  (`CompanyScopedManager`, hace fallar cualquier query sobre un modelo
  con scope de empresa que no pase por `.for_company(company)`).
- Suite de aislamiento multiempresa (gate obligatorio desde esta fase,
  ver `docs/TESTING.md`): 22 tests cubriendo registro, login, logout,
  creación de empresa, y — el foco de la fase — que un usuario nunca ve
  ni accede (404, no 403) a datos de una empresa ajena.
- Verificado localmente: migraciones aplicadas desde cero contra
  PostgreSQL real, suite completa en verde, y un recorrido manual por
  HTTP (2 usuarios, 2 empresas) confirmando que cada uno solo ve la
  suya.
- Sin productos, ventas, inventario ni asistente todavía (eso es Fase 3
  en adelante).

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
  real), job frontend (`lint` + `build`), y job `compose` que ejecuta
  `docker compose up --build` real y verifica backend y frontend por
  HTTP — permite validar la Fase 1 sin necesidad de Docker local.
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
