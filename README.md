# MAGAVI

Asistente inteligente de gestión mobile-first para micro y pequeñas
empresas chilenas. El usuario administra su negocio conversando con la
app (texto o foto de documentos), no llenando formularios.

> "El emprendedor no debería tener que aprender a usar un software
> complejo. Debería poder decirle al sistema qué necesita hacer."

## Estado actual

**Fase 0 — Arquitectura y planificación.** Aún no hay código de
aplicación. Este repositorio contiene por ahora la documentación de
diseño que guía la construcción del MVP en fases incrementales y
verificables.

No avanzamos de fase sin que la anterior esté probada y aprobada.

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

Por ahora, los cambios relevantes son a la documentación de `docs/`. La
implementación de código comienza en la Fase 1 del roadmap, tras
aprobación explícita de la Fase 0.
