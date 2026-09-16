# MAGAVI — Backend

Django + Django REST Framework. Ver documentación del proyecto en
`../docs/` y el estado general en `../README.md`.

## Desarrollo local (sin Docker)

Requiere una instancia de PostgreSQL accesible.

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env  # y ajustar valores
python manage.py migrate
python manage.py runserver
```

## Tests y lint

```
ruff check .
pytest
```

## Apps

`core` (utilidades transversales: health check, `tenancy.py` con
`get_current_company`, `managers.py` con `CompanyScopedManager`),
`accounts` (usuario custom + JWT), `companies` (Company, CompanyUser,
Module, CompanyModule), `catalog` (Product), `inventory`
(InventoryMovement + Tool Layer `ajustar_inventario`), `sales` (Sale,
SaleItem + Tool Layer `crear_venta`), `purchases` (Purchase,
PurchaseItem + Tool Layer `registrar_compra`), `cashbox` (CashMovement +
Tool Layer de solo lectura `obtener_resumen`, la fuente única de verdad
del dashboard), `audit` (AuditLog append-only, escrito por el Tool
Layer; sin endpoints todavía), `assistant` (Conversation, Message,
PendingAction; `intents.py` registra los intents soportados y los
ejecuta contra el Tool Layer existente; `services.py` implementa la
máquina de confirmación `proponer_intent`/`confirmar_intent`/
`cancelar_intent` — ver `docs/ARCHITECTURE.md` #3.4), `documents`. Ver
`docs/ARCHITECTURE.md` para el propósito de cada una. `documents` sigue
vacía hasta la Fase 9.

## Endpoints

- `GET /api/health/` — healthcheck público, sin autenticación.
- `POST /api/auth/register/` — registro (devuelve access + refresh).
- `POST /api/auth/login/` — login con `email`/`password` (devuelve access
  + refresh).
- `POST /api/auth/refresh/` — refresca el access token.
- `POST /api/auth/logout/` — invalida (blacklist) el refresh token.
- `GET /api/auth/me/` — usuario autenticado actual.
- `GET/POST /api/companies/` — "mis empresas" / crear empresa (el creador
  queda como `owner`).
- `GET /api/companies/<id>/` — detalle, solo si el usuario tiene
  membresía activa (404 si no, nunca 403, para no confirmar existencia).
- `GET/POST /api/products/` — listar/crear productos. `POST` acepta
  `initial_stock` opcional (siembra el stock inicial vía
  `ajustar_inventario`). `GET ?low_stock=true` filtra los productos con
  `current_stock <= low_stock_threshold`.
- `GET/PATCH/PUT /api/products/<id>/` — detalle/edición. Sin `DELETE`
  (405): no hay borrado físico, se desactiva con `is_active`.
- `POST /api/products/<id>/adjust-stock/` — ajuste manual de stock
  (`{"cantidad": "-3", "motivo": "..."}`); rechaza dejar el stock en
  negativo (ver `docs/DECISIONS.md` ADR-009).
- `GET/POST /api/sales/` — listar (con filtros opcionales `?from=` /
  `?to=`, formato `YYYY-MM-DD`) / crear una venta:
  `{"items": [{"product_id": 1, "quantity": "3", "unit_price": "2500.00"}], "customer_name": "..."}`
  (`unit_price` es opcional, por defecto `Product.default_price`).
  Actualiza stock e ingreso de caja en la misma transacción (Tool Layer
  `crear_venta`).
- `GET /api/sales/summary/` — `{"today": {"total": ..., "count": ...},
  "week": {...}}`, soporte directo a "¿cuánto vendí hoy?" del guion de
  demo.
- `GET/POST /api/purchases/` — análogo a `/api/sales/`: listar (con
  filtros `?from=`/`?to=`) / registrar una compra:
  `{"supplier_name": "...", "items": [{"product_id": 1, "quantity": "20", "unit_cost": "1500.00"}]}`
  (`unit_cost` opcional, por defecto `Product.default_cost`). Sube stock
  y registra el egreso de caja (Tool Layer `registrar_compra`).
- `GET /api/purchases/summary/` — compras/egresos de hoy y de la semana.
- `GET /api/cashbox/summary/` — fuente única de verdad de "cómo va el
  negocio hoy": `{"cash": {"today": {"income","expense","balance"},
  "week": {...}}, "sales": {"today": {"total","count"}, "week": {...}},
  "low_stock_products": [...]}`. Reutiliza `sales`/`catalog` sin
  duplicar lógica; el asistente (Fase 8) consumirá este mismo Tool Layer
  (`cashbox/services.py::obtener_resumen`) directamente, sin pasar por
  HTTP.
- `GET/POST /api/assistant/conversations/` — "mis conversaciones" / crear
  una nueva.
- `GET/POST /api/assistant/conversations/<id>/messages/` — historial de
  una conversación / agregar un mensaje.
- `POST /api/assistant/intents/` —
  `{"intent": "crear_venta", "parameters": {...}, "conversation_id": opcional}`.
  Intents soportados: `crear_venta`, `registrar_compra`,
  `ajustar_inventario` (mutantes, requieren confirmación) y
  `consultar_ventas`, `consultar_stock_bajo` (de solo lectura, se
  ejecutan de inmediato).
- `POST /api/assistant/intents/<id>/confirm/` — ejecuta de verdad una
  propuesta pendiente (revalidándola por completo primero — el estado
  pudo cambiar desde que se propuso).
- `POST /api/assistant/intents/<id>/cancel/` — cancela una propuesta
  pendiente.
- `POST /api/assistant/chat/` —
  `{"message": "Vendí 3 cafés a 2500", "conversation_id": opcional}`.
  Punto de entrada en lenguaje natural (Fase 8): el Orchestrator
  (`assistant/orchestrator.py`) arma el prompt, llama al `LLMProvider`
  configurado (`LLM_PROVIDER`: `ollama` en producción, `deepseek_dev`
  solo para desarrollo — ver `docs/DECISIONS.md` ADR-004/ADR-010),
  valida la salida y la propone igual que `/api/assistant/intents/`
  — toda mutación sigue requiriendo confirmación explícita, sin
  excepción para el LLM. Si no logra interpretar el mensaje, responde
  pidiendo aclaración en vez de fallar.

Todos los endpoints de negocio requieren el header `X-Company-Id` con la
empresa activa; ver `core/tenancy.py`.

## LLM del asistente

- `LLM_PROVIDER=ollama` (default): apunta a un Ollama self-hosted
  (`LLM_OLLAMA_BASE_URL`, `LLM_OLLAMA_MODEL`). Servicio opcional en
  `docker-compose.yml` bajo el perfil `llm` (`docker compose --profile
  llm up`), apagado por defecto — requiere cómputo real.
- `LLM_PROVIDER=fake`: usado por los tests automáticos
  (`assistant/llm_providers.py::FakeLLMProvider`), sin red ni GPU.
- `LLM_PROVIDER=deepseek_dev` + `DEEPSEEK_API_KEY`: **solo para
  desarrollo/pruebas** (ver `docs/DECISIONS.md` ADR-010) — nunca en
  producción. Se verifica con un job manual de GitHub Actions
  (`.github/workflows/llm-check.yml`, disparado a mano desde la pestaña
  Actions), usando el secreto `DEEPSEEK_API_KEY` del repositorio — no
  desde el entorno de desarrollo local, que tiene bloqueada esa salida
  de red.
