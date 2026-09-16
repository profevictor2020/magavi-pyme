# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Fase 8 — LLM y tool calling real

- `LLMProvider` (`assistant/llm_providers.py`): interfaz + tres
  implementaciones — `OllamaLLMProvider` (producción, self-hosted, ver
  ADR-004), `DeepSeekLLMProvider` (**solo desarrollo/pruebas**, nueva
  decisión documentada como ADR-010: usar la API alojada de DeepSeek
  como excepción acotada, nunca como proveedor de producción) y
  `FakeLLMProvider` (tests, sin red ni GPU).
- Orchestrator (`assistant/orchestrator.py`): arma el prompt (system
  fijo + catálogo de la empresa), llama al `LLMProvider`, parsea/valida
  el JSON de intent (con un reintento si la salida no es válida),
  reutiliza `proponer_intent` de la Fase 7 sin cambios, y registra la
  conversación (`Conversation`/`Message`). Defensa contra prompt
  injection: el mensaje del usuario nunca se concatena al system
  prompt, y cualquier clave extra que el modelo agregue a su respuesta
  (p.ej. intentando marcar una acción como ya confirmada) se ignora —
  toda mutación sigue pasando por la confirmación explícita del backend.
- Endpoint `POST /api/assistant/chat/` (texto libre → intent → misma
  máquina de confirmación de la Fase 7).
- `docker-compose.yml`: servicio opcional `llm-inference` (Ollama) bajo
  el perfil `llm`, apagado por defecto (no lo toca `docker compose up`
  ni el job `compose` de CI) — requiere cómputo real, no disponible en
  este entorno de desarrollo.
- Verificación real de DeepSeek separada del pipeline normal: comando
  `manage.py smoke_test_llm` + workflow manual
  `.github/workflows/llm-check.yml` (`workflow_dispatch`, usa el
  secreto `DEEPSEEK_API_KEY` del repositorio) — nunca se ejecuta
  automáticamente en cada push.
- 15 tests nuevos (132 en total): unit del Orchestrator (interpretación
  correcta, reintento ante JSON inválido, bloque markdown tolerado,
  intent `no_entendido`, registro de conversación) y un bloque
  específico de **prompt injection** (mensajes que intentan saltarse la
  confirmación, o una respuesta de LLM con claves falsificadas
  simulando confirmación, nunca ejecutan nada sin pasar por el flujo
  normal) e integración del endpoint de chat.
- Verificado localmente: suite completa en verde, sin cambios de
  esquema, y un recorrido manual con tráfico HTTP real (no solo mocks en
  Python): un servidor local que imita el formato de la API de Ollama,
  para probar de verdad el cliente HTTP de `OllamaLLMProvider` — "Vendí
  3 cafés a 2500" por HTTP → propuesta → confirmación → venta
  registrada → reflejada en `/api/sales/summary/`.
- Sin captura de documentos todavía (eso es Fase 9 en adelante).

### Fase 7 — Capa de herramientas para el asistente (sin LLM)

- Modelos `Conversation`, `Message` y **`PendingAction`** (nueva
  entidad, no estaba en el modelo original — documentada en
  `docs/DATA_MODEL.md` — materializa la máquina de estados de
  confirmación `pending → confirmed/cancelled/expired`).
- Registro de intents soportados (`assistant/intents.py`):
  `crear_venta`, `registrar_compra`, `ajustar_inventario` (mutantes,
  requieren confirmación) y `consultar_ventas`, `consultar_stock_bajo`
  (solo lectura, se ejecutan de inmediato). Cada intent reutiliza sin
  cambios el Tool Layer ya construido (`crear_venta`,
  `registrar_compra`, `ajustar_inventario`, y las nuevas funciones de
  solo lectura `sales.consultar_ventas` / `catalog.consultar_stock_bajo`,
  extraídas de `SaleSummaryView`/`cashbox.obtener_resumen` para
  eliminar duplicación).
- Máquina de confirmación (`assistant/services.py`):
  `proponer_intent` (valida forma; ejecuta de inmediato si es de solo
  lectura, o crea una propuesta pendiente si es mutante — sin ejecutar
  nada todavía), `confirmar_intent` (**revalida por completo** los
  parámetros antes de ejecutar, porque el estado del negocio pudo
  cambiar entre proponer y confirmar) y `cancelar_intent`. Propuestas
  pendientes expiran a los 10 minutos.
- Endpoints: `GET/POST /api/assistant/conversations/`,
  `GET/POST /api/assistant/conversations/<id>/messages/`,
  `POST /api/assistant/intents/`,
  `POST /api/assistant/intents/<id>/confirm/`,
  `POST /api/assistant/intents/<id>/cancel/`.
- **Bug real encontrado y corregido antes de empujar**: al marcar una
  propuesta vencida como `expired`, la excepción se lanzaba dentro del
  mismo `transaction.atomic()` que guardaba ese estado, así que el
  rollback deshacía el propio guardado. Se corrigió separando el
  guardado (que debe persistir) del `raise` (que ahora ocurre después,
  fuera de la transacción).
- 26 tests nuevos (117 en total): unit de cada intent (válido e
  inválido, incluyendo doble confirmación, expiración, y revalidación
  cuando el stock cambia entre proponer y confirmar) e integración de
  la API cubriendo el flujo completo propuesta → confirmación →
  ejecución → auditoría, más el gate obligatorio de seguridad (un
  intent que referencia un producto/empresa ajena es rechazado).
- Verificado localmente: migraciones desde cero, suite completa en
  verde, y un recorrido manual por HTTP enviando a mano el JSON que
  "debería" producir un LLM (`{"intent": "crear_venta", ...}`),
  confirmando, y viendo la venta y el stock reflejados — el guion de
  demo completo funcionando sin ningún LLM todavía.
- Sin LLM real todavía (eso es Fase 8).

### Fase 6 — Caja y dashboard/resumen

- Tool Layer de solo lectura `obtener_resumen` (`cashbox/services.py`):
  fuente única de verdad de "cómo va el negocio hoy" — caja
  (ingreso/egreso/balance), ventas, y productos con stock bajo, para
  hoy y para la semana. Reutiliza `Sale`/`CashMovement`/`Product` sin
  duplicar lógica de negocio.
- Endpoint `GET /api/cashbox/summary/`.
- Refactor: se extrajo `core/dates.py::today_and_week_start()` (límites
  de "hoy"/"esta semana" en hora de Chile) para eliminar la duplicación
  que ya existía entre `sales` y `purchases`, y que ahora también usa
  `cashbox`.
- **Ajuste de alcance documentado** (`docs/ROADMAP.md` Fase 6): se
  difiere la vista de dashboard del frontend a la Fase 10, para no
  construir pantallas con login/selección de empresa (que no existen
  todavía) antes de tiempo y tener que rehacerlas.
- 11 tests nuevos (91 en total): unit de los cálculos de agregación,
  incluyendo un caso explícito de un movimiento a las 23:30 hora de
  Chile para verificar que los límites de "hoy" usan la zona horaria
  local y no UTC; integración del endpoint con el gate obligatorio de
  aislamiento multiempresa.
- Verificado localmente: sin cambios de esquema (`makemigrations
  --check` limpio), suite completa en verde, y recorrido manual por
  HTTP cargando productos/ventas/compras y confirmando que el resumen
  coincide exactamente con `/api/sales/summary/` y
  `/api/purchases/summary/`.
- Sin asistente conversacional todavía (eso es Fase 7 en adelante).

### Fase 5 — Compras

- Modelos `Purchase`/`PurchaseItem` (`purchases`), simétricos a
  `Sale`/`SaleItem`.
- Tool Layer `registrar_compra` (`purchases/services.py`): valida
  ítems, calcula totales (con `unit_cost` opcional, por defecto
  `Product.default_cost`), sube stock reutilizando sin cambios
  `ajustar_inventario`, registra el egreso de caja y una entrada de
  auditoría, todo en una transacción atómica.
- Endpoints: `GET/POST /api/purchases/` (con filtros de fecha) y `GET
  /api/purchases/summary/` (compras de hoy/semana), análogos a ventas.
- 18 tests nuevos (80 en total): unit del Tool Layer (totales, aumento
  de stock, movimiento de caja, atomicidad, rechazo de producto de otra
  empresa) e integración de la API, incluyendo el gate obligatorio de
  aislamiento multiempresa.
- Verificado localmente: migraciones desde cero, suite completa en
  verde, y recorrido manual por HTTP registrando una compra y
  confirmando que sube el stock y baja la caja — incluyendo una venta y
  una compra conviviendo sobre el mismo producto sin interferirse.
- Sin dashboard ni asistente todavía (eso es Fase 6 en adelante).

### Fase 4 — Ventas

- Modelos `Sale`/`SaleItem` (`sales`), `CashMovement` (`cashbox`) y
  `AuditLog` (`audit`, append-only — no editable/borrable ni desde el
  admin de Django).
- Tool Layer `crear_venta` (`sales/services.py`): único punto de
  escritura de ventas. Valida ítems, calcula totales, descuenta stock
  reutilizando sin cambios `ajustar_inventario` (Fase 3), registra el
  ingreso de caja y una entrada de auditoría — todo en una única
  transacción atómica (si un ítem no tiene stock suficiente, no queda
  venta, movimiento de inventario ni de caja huérfanos).
- Decisión explícita documentada (ADR-009, reutilizada de Fase 3): no se
  permite stock negativo, tampoco en ventas.
- Endpoints: `GET/POST /api/sales/` (con filtros de fecha) y `GET
  /api/sales/summary/` (ventas de hoy/semana — soporte directo al "¿cuánto
  vendí hoy?" del guion de demo).
- 20 tests nuevos (62 en total): unit del Tool Layer (cálculo de
  totales, descuento de stock, movimiento de caja, atomicidad ante
  fallo de un ítem, rechazo de producto de otra empresa) e integración
  de la API (creación, listado, resumen, y el gate obligatorio de
  aislamiento multiempresa).
- Verificado localmente: migraciones desde cero, suite completa en
  verde, y recorrido manual por HTTP replicando el guion de demo
  (vender 3 cafés, ver el resumen de "hoy" actualizarse, ver el stock
  descontado, e intentos inválidos correctamente rechazados).
- Sin compras ni asistente todavía (eso es Fase 5 en adelante).

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
