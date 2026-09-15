# MAGAVI

Asistente inteligente de gestión mobile-first para micro y pequeñas
empresas chilenas. El usuario administra su negocio conversando con la
app (texto o foto de documentos), no llenando formularios.

> "El emprendedor no debería tener que aprender a usar un software
> complejo. Debería poder decirle al sistema qué necesita hacer."

## Estado actual

**Fase 1 — Estructura del proyecto + Docker + PostgreSQL.** Existe la
estructura base del backend (Django + DRF, apps de dominio vacías) y del
frontend (React + Vite), levantables con Docker Compose contra
PostgreSQL. Todavía no hay modelos de negocio, autenticación ni UI real —
eso empieza en la Fase 2.

No avanzamos de fase sin que la anterior esté probada y aprobada.

## Cómo levantar el entorno

```
cp .env.example .env   # y ajustar valores (nunca commitear .env)
docker compose up --build
```

- Backend: http://localhost:8000/api/health/
- Frontend: http://localhost:5173

Ver `backend/README.md` y `frontend/README.md` para desarrollo sin
Docker.

## Documentación

- [`docs/PRODUCT.md`](docs/PRODUCT.md) — visión de producto, alcance y
  fuera de alcance del MVP.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — arquitectura del
  sistema, multi-tenancy, asistente conversacional y tool-calling, IA
  privada, OCR.
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — modelo de datos y
  diagrama de entidades.
- [`docs/SECURITY.md`](docs/SECURITY.md) — modelo de amenazas y
  estrategia de seguridad.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — fases de desarrollo, con
  objetivo, alcance, tests y criterio de aceptación de cada una.
- [`docs/TESTING.md`](docs/TESTING.md) — estrategia de pruebas.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — decisiones arquitectónicas
  (ADR) y su justificación.

## Stack (resumen; justificación completa en `docs/DECISIONS.md`)

- **Frontend:** React + Vite, PWA instalable, mobile-first.
- **Backend:** Django + Django REST Framework.
- **Base de datos:** PostgreSQL.
- **Async/colas:** Celery + Redis (OCR, estructuración de documentos).
- **IA privada:** modelo open-source autoalojado (candidatos:
  Qwen2.5-7B-Instruct / Llama-3.1-8B-Instruct) vía Ollama/vLLM — nunca un
  proveedor externo en producción, y sin acceso directo del LLM a la
  base de datos.
- **OCR:** PaddleOCR/docTR, open-source, autoalojado.
- **Infraestructura:** Docker, Docker Compose, NGINX, Linux.

## Cómo contribuir en esta etapa

Seguimos el roadmap de `docs/ROADMAP.md` fase por fase. Cada fase
requiere tests en verde, prueba manual documentada y aprobación explícita
antes de avanzar a la siguiente.
