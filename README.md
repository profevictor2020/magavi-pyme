# MAGAVI

Asistente inteligente de gestión mobile-first para micro y pequeñas
empresas chilenas. El usuario administra su negocio conversando con la
app (texto o foto de documentos), no llenando formularios.

> "El emprendedor no debería tener que aprender a usar un software
> complejo. Debería poder decirle al sistema qué necesita hacer."

## Estado actual

**Despliegue.** Preparado para correr en una VM real (self-hosting
completo, sin proveedores externos de LLM/OCR, sin costo) usando el tier
Always Free de Oracle Cloud — ver `docs/DEPLOY.md` para la guía paso a
paso y `docs/DECISIONS.md` ADR-014 para el porqué de esta elección.

**Fase 12 — Demo MVP.** Fase de integración y validación, sin
funcionalidad nueva: el guion de demo completo (abrir MAGAVI desde un
celular → iniciar sesión → "¿cuánto vendí hoy?" → "Vendí 3 cafés a
$2.500" → confirmar → inventario/caja actualizados → volver a preguntar
"¿cuánto vendí hoy?" y ver el cambio → fotografiar una boleta de compra
→ revisar → confirmar → inventario actualizado, todo con una segunda
empresa en paralelo sin ningún dato cruzado) ahora tiene un test E2E
real (Playwright, viewport móvil) que lo corre de punta a punta contra
el stack completo — backend, worker de Celery, Redis, OCR real con
Tesseract y un LLM de prueba determinístico (`backend/scripts/
e2e_fake_llm.py`, habla el mismo protocolo que Ollama) — en su propio
job de CI (`e2e`). Se ejecutó además a mano, con capturas de pantalla
de cada paso del guion. **Con esto, las Fases 0–12 del roadmap original
quedan completas.**

**Fase 11 — Seguridad, auditoría y pruebas integrales.** Endurecimiento
de seguridad de punta a punta: rate limiting real (login/asistente/
documentos, separado también por empresa activa, no solo por usuario),
`AuditLog` ahora instrumentado en todos los flujos de escritura
relevantes (ventas, compras, ajustes de inventario, confirmación/rechazo
de documentos, login/logout/registro, creación de empresa) en vez de
solo tener el modelo sin usar, cabeceras de seguridad de producción
(HSTS, cookies seguras, redirect a HTTPS) activas automáticamente fuera
de modo debug, y dependencias actualizadas a versiones sin
vulnerabilidades conocidas (Django, DRF, simplejwt, Pillow) con
`pip-audit`/`npm audit` bloqueando CI de ahí en adelante. De paso se
corrigió una condición de carrera real: confirmar el mismo documento dos
veces (doble tap, reintento de red) podía registrar la compra/venta dos
veces — ahora está serializado con bloqueo de fila. Se ejecutó a mano un
checklist de seguridad completo (login roto, acceso cruzado por id,
subida de archivo inválida, intento de prompt injection contra un LLM
adversarial de prueba) — ver `docs/SECURITY.md` §14 para el detalle y
resultado de cada caso: ningún hallazgo crítico abierto. PostgreSQL Row
Level Security queda documentado como mejora diferida, no bloqueante
(`docs/DECISIONS.md` ADR-013).

**Fase 10 — PWA mobile-first y UX final.** El frontend dejó de ser un
placeholder: ahora es una PWA instalable, de una sola columna, con el
**chat como pantalla principal** (`ChatPage`) — enviar un mensaje como
"Vendí 3 cafés a 2500" muestra la propuesta del asistente con botones de
confirmar/cancelar, y el resultado registrado, todo sin salir del chat.
Las pantallas tradicionales (productos, ventas, compras, documentos,
caja) están pulidas para uso con una mano en celular, con navegación
inferior fija. La captura de documentos ahora tiene UI real: fotografiar
con la cámara del celular (`<input capture>`), revisar/corregir los
datos extraídos y confirmar. Manifest + Service Worker (cachea solo el
"shell", nunca datos de negocio) hacen la app instalable. Todo el
recorrido completo (registro → crear empresa → crear producto → vender
por chat → confirmar → ver caja actualizada → fotografiar una factura →
confirmar como compra) se probó de punta a punta en un navegador real
(Chromium headless, viewport móvil), no solo con `curl` — lo que además
encontró y permitió corregir un bug real de CORS (`X-Company-Id` no
estaba permitido, ver `docs/DECISIONS.md` ADR-012) que ninguna prueba
anterior vía `curl` podía detectar.

**Fase 9 — Captura de documentos y OCR.** Ya se puede fotografiar/subir
una boleta o factura (`POST /api/documents/`): un worker de Celery
extrae el texto con OCR real (Tesseract, 100% local — ver
`docs/DECISIONS.md` ADR-011) y lo estructura reutilizando el mismo LLM
del asistente (proveedor, ítems, total). El usuario revisa y corrige los
datos propuestos y recién ahí confirma (`POST
/api/documents/<id>/confirm/`), lo que registra la compra/venta real
reutilizando el Tool Layer existente (`registrar_compra`/`crear_venta`)
— nunca se registra nada solo por subir o procesar un documento. El
pipeline completo (subida → OCR real → estructuración → confirmación →
stock y caja actualizados) se probó de punta a punta con infraestructura
real (Redis + Celery + Tesseract), no solo con mocks.

**Fase 8 — LLM y tool calling real.** El asistente ya entiende lenguaje
natural: `POST /api/assistant/chat/` arma el prompt, llama al
`LLMProvider` configurado, valida la salida contra el mismo contrato de
intents de la Fase 7 y la propone (con confirmación obligatoria para
toda mutación — el LLM nunca ejecuta nada por sí mismo). El proveedor de
producción es self-hosted (`ollama`, sin ejecutar aún en este entorno
sin GPU); para pruebas de desarrollo existe una excepción documentada y
acotada (`deepseek_dev`, ver `docs/DECISIONS.md` ADR-010), verificable
con un job manual de GitHub Actions.

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

### Si no tienes Docker disponible

El workflow de CI (`.github/workflows/ci.yml`, job `compose`) ejecuta
exactamente este mismo `docker compose up` en GitHub Actions en cada
push, y falla si el backend o el frontend no responden. Puedes verificar
la Fase 1 (y cualquier fase futura) revisando que ese check esté en verde
en la pestaña **Actions** del repositorio, sin necesidad de instalar
Docker localmente.

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
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — guía de despliegue en producción
  (Oracle Cloud Always Free).

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
