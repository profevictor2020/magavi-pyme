# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Unreleased]

### Despliegue en producción

Preparación para correr en una VM real (self-hosting completo, ver
`docs/DECISIONS.md` ADR-014 y `docs/DEPLOY.md`), sin cambiar el
comportamiento de desarrollo (`docker-compose.yml` intacto).

- `docker-compose.prod.yml` (nuevo, autocontenido — no se combina con
  `docker-compose.yml`): backend con gunicorn, worker, Postgres/Redis
  sin puertos publicados al host, frontend como build de producción
  servido por NGINX, volumen `media_data` compartido entre
  backend/worker/frontend para persistir documentos subidos.
- `frontend/Dockerfile.prod` + `frontend/nginx.conf` (nuevos): build de
  producción (`npm run build`) servido por NGINX, que además hace de
  reverse proxy hacia el backend (`/api/`) y sirve `/media/` desde el
  volumen compartido — mismo origen en el navegador, sin necesitar CORS
  en producción.
- `backend`: `whitenoise` para servir los estáticos de Django (admin,
  DRF browsable API) desde el propio proceso de gunicorn;
  `collectstatic` automático en `docker-entrypoint.sh`. Al definir
  `STORAGES` para esto se encontró y corrigió un bug real: sin declarar
  también la clave `"default"`, Django dejaba de aplicar el storage por
  defecto para archivos subidos por usuarios (documentos/OCR),
  rompiendo 17 tests existentes — se detectó corriendo la suite
  completa antes de dar el cambio por terminado, no solo el flujo que
  se estaba tocando.
- `.env.prod.example` (nuevo): plantilla de variables de producción
  (`DJANGO_DEBUG=false`, sin TLS todavía por no haber dominio propio,
  etc.).
- `docs/DEPLOY.md` (nuevo): guía paso a paso para Oracle Cloud Always
  Free, incluyendo el firewall de dos capas de OCI (Security List +
  iptables de la VM — bloquea el puerto 80 aunque solo se configure
  una de las dos).

### Fase 12 — Demo MVP

Fase de integración y validación (sin funcionalidad nueva, ver
`docs/ROADMAP.md`): confirma que el guion de demo completo del MVP
funciona de punta a punta.

- `backend/scripts/e2e_fake_llm.py`: stub HTTP determinístico que habla
  el mismo protocolo que Ollama (compatible con OpenAI), usado SOLO por
  el job de CI `e2e` — distingue el prompt del asistente conversacional
  del prompt de estructuración de documentos, y resuelve `product_id`
  leyendo el catálogo que el propio backend incluye en cada prompt (no
  asume ids fijos, porque no son predecibles en una corrida de punta a
  punta).
- `docker-compose.e2e.yml`: override que reemplaza el LLM de producción
  (perfil `llm`, apagado por defecto) por el stub anterior — nunca se
  usa en `docker compose up` normal ni en producción.
- `frontend/e2e/demo.spec.ts` (Playwright + `@playwright/test`, viewport
  móvil `Pixel 7`): dos tests. El primero cubre los 7 pasos del guion de
  demo (`docs/ROADMAP.md` Fase 12: iniciar sesión → "¿cuánto vendí hoy?"
  → "Vendí 3 cafés a 2500" → confirmar → caja/inventario actualizados →
  volver a preguntar y ver el cambio → fotografiar una factura → revisar
  → confirmar → inventario actualizado). El segundo prueba el punto 8
  (aislamiento): una empresa nueva en paralelo nunca ve los datos de la
  primera.
- Nuevo job `e2e` en CI (`.github/workflows/ci.yml`): levanta el stack
  completo real (`docker-compose.yml` + `docker-compose.e2e.yml`),
  instala Chromium (`playwright install --with-deps`) y corre el guion
  contra la app real — no contra mocks. Sube el reporte HTML de
  Playwright como artefacto si algo falla.
- Verificado además a mano (no solo el test automático): se corrió el
  mismo recorrido completo contra el stack real (Postgres, Redis,
  Celery, Tesseract, el LLM de prueba) con capturas de pantalla de cada
  paso, incluyendo la verificación en vivo de que una segunda empresa
  ("Ferretería Pedro") nunca ve nada de la primera ("Almacén Marcela").
- **Bug real encontrado y corregido en el propio script de verificación
  manual** (no en la app): el sufijo usado para generar un RUT único
  por corrida tomaba los primeros dígitos de `Date.now()`, que casi no
  cambian entre corridas separadas por minutos — dos ejecuciones
  cercanas en el tiempo generaban el mismo RUT y la creación de la
  segunda empresa fallaba con "Ya existe company con este rut." Se
  corrigió usando los últimos dígitos (más volátiles). El mismo bug
  existía en `frontend/e2e/demo.spec.ts` y se corrigió ahí también antes
  de que llegara a CI.
- **Bug real de CI encontrado y corregido en el primer run del job
  `e2e`** (este sandbox no tiene Docker, así que el job nunca se pudo
  probar localmente antes de empujarlo): `docker compose up` corría
  antes que `npm ci`, y el contenedor `frontend` (que corre como root y
  comparte `./frontend` con el host vía bind mount) dejaba ese
  directorio en un estado que bloqueaba el `npm ci` posterior del
  runner (no-root) con `EACCES`. El resto de la infraestructura
  (Postgres, Redis, Celery, Tesseract, el LLM de prueba, el propio
  backend) se levantó bien a la primera. Corregido invirtiendo el
  orden: instalar dependencias de Node y el navegador de Playwright
  antes de levantar `docker compose`.
- Con esto, las Fases 0–12 del roadmap original del MVP quedan
  completas.

### Fase 11 — Seguridad, auditoría y pruebas integrales

- **Dependencias actualizadas** tras un escaneo con `pip-audit` que
  encontró 50 vulnerabilidades conocidas en 5 paquetes: Django
  (`5.0.14` → `5.2.17`), `djangorestframework` (`3.15.2` → `3.17.2`),
  `djangorestframework-simplejwt` (`5.3.1` → `5.5.1`), Pillow (`10.4.0`
  → `12.3.0`) y pytest (`8.4.2` → `9.1.1`, dev). Se eliminó
  `python-dotenv` de `requirements.txt` (dependencia sin ningún uso real
  en el código, y también vulnerable). Suite completa (159 tests) verde
  después de la actualización, sin cambios de comportamiento.
- **Rate limiting real** (`core/throttling.py::CompanyScopedRateThrottle`,
  variante de `ScopedRateThrottle` que separa el cupo también por
  empresa activa vía `X-Company-Id`, no solo por usuario/IP): scope
  `auth` (login/registro/refresh/logout, 10/min) en nuevas
  `LoginView`/`LogoutView`/`RefreshView` (`accounts/views.py`), scope
  `assistant` (chat/proponer/confirmar intent, 30/min), scope
  `documents` (solo la subida, 20/min, ver `documents/views.py`).
  `conftest.py` nuevo: limpia el cache antes/después de cada test para
  que los contadores de throttle no se filtren entre tests.
- **`AuditLog` instrumentado de verdad** (antes el modelo existía pero
  solo `sale.create`/`purchase.create` lo usaban, y siempre con
  `source="api"` sin importar el origen real): nuevo
  `audit_source_for_origen()` (`audit/services.py`) mapea el `origen`
  interno del Tool Layer (`manual`/`assistant`/`document`) al
  vocabulario de `AuditLog.source` (`ui`/`assistant`/`document`);
  `ajustar_inventario` ahora audita `inventory.adjust` (cubre el ajuste
  manual y cada movimiento disparado por una venta/compra);
  `DocumentConfirmView`/`DocumentRejectView` auditan
  `document.confirm`/`document.reject`; `CompanyListCreateView` audita
  `company.create`; nuevas `LoginView`/`LogoutView` y `RegisterView`
  auditan `auth.login`/`auth.logout`/`auth.register`. El admin de
  `AuditLog` ahora tampoco permite agregar entradas a mano (ya no
  permitía editar/borrar).
- **Bug real corregido: condición de carrera en `DocumentConfirmView`**
  (ver docs/SECURITY.md #8) — confirmar el mismo documento dos veces
  simultáneamente (doble tap, reintento de red) podía pasar el chequeo
  de "ya confirmado" en ambas antes de que cualquiera alcanzara a
  actualizar el estado, registrando dos compras/ventas por un solo
  documento. Corregido envolviendo el chequeo + ejecución + cambio de
  estado en `transaction.atomic()` + `select_for_update()` sobre la fila
  del documento — la segunda confirmación ahora espera a la primera y
  ve el estado ya actualizado. Se preservó cuidadosamente el orden
  "verificar dueño del recurso antes que validar el body" (un test de
  aislamiento existente detectó una regresión propia en el primer
  intento de este fix, donde un documento ajeno con un body inválido
  devolvía 400 en vez de 404).
- **Cabeceras de seguridad de producción**: `SECURE_SSL_REDIRECT`,
  `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
  `SECURE_HSTS_SECONDS`/`INCLUDE_SUBDOMAINS`/`PRELOAD`, todas activadas
  automáticamente solo cuando `DJANGO_DEBUG=false` (nunca en dev/CI, que
  corren con `DEBUG=True` — evita romper el cliente de tests o
  `docker compose` sin TLS real delante). Verificado con
  `python manage.py check --deploy` (0 hallazgos).
- **Escaneo de dependencias en CI**: `pip-audit` (backend) y
  `npm audit --audit-level=moderate` (frontend) corren en cada push y
  **bloquean el pipeline** ante una vulnerabilidad conocida — antes no
  corrían en absoluto pese a estar documentados desde la Fase 0.
- **Batería de seguridad consolidada** (`core/test_security.py`, 13
  tests nuevos): acceso anónimo rechazado en los endpoints de negocio,
  `X-Company-Id` obligatorio, rate limiting end-to-end (la request 11 a
  `/api/auth/login/` responde 429), y un test por flujo de escritura
  verificando que efectivamente queda su `AuditLog` con el `source`
  correcto.
- **Checklist manual de seguridad ejecutado y documentado**
  (`docs/SECURITY.md` #14): login roto (password incorrecta, intento de
  inyección SQL en el email, mensaje de error idéntico entre usuario
  inexistente y password incorrecta), acceso cruzado por id en tres
  variantes (IDOR), subida de archivo inválida en dos variantes, e
  intento de prompt injection contra un LLM adversarial de prueba que
  intentaba auto-marcarse como "ya confirmado" — el backend ignoró por
  completo esos campos falsos y exigió la confirmación humana normal.
  Ningún hallazgo crítico abierto.
- **PostgreSQL Row Level Security: diferido explícitamente**, no
  implementado esta fase — ver `docs/DECISIONS.md` ADR-013 para el
  análisis de costo/riesgo y las condiciones bajo las que se revisitaría.
- Suite final: 172 tests (159 + 13 nuevos), `ruff check .` limpio,
  `pip-audit`/`npm audit` sin hallazgos.

### Fase 10 — PWA mobile-first y UX final

- Frontend real (antes solo el placeholder de la Fase 1): SPA con
  `react-router-dom`, CSS mobile-first escrito a mano (sin framework de
  componentes), dos React Context (`AuthContext`, `CompanyContext`) —
  ver la justificación completa de cada decisión de stack en
  `docs/DECISIONS.md` ADR-012.
- `src/api/client.ts`: cliente HTTP con reintento automático de refresh
  de token JWT ante un 401 (y logout automático si el refresh también
  falla), y `src/api/endpoints.ts` con funciones tipadas por recurso que
  reciben la empresa activa **explícita** como parámetro (en vez de
  leerla implícitamente de `localStorage` al momento del fetch, que
  tenía una condición de carrera real entre efectos de React).
- Pantallas de auth y empresa: `LoginPage`, `RegisterPage`, `CompanyPage`
  (crear la primera empresa o cambiar entre las existentes).
- **`ChatPage`**, la pantalla principal de la app (ver
  `docs/ARCHITECTURE.md` #3.1): conversación con el asistente, cada
  propuesta de intent mutante se muestra como una tarjeta con botones
  "Confirmar"/"Cancelar" (nunca se ejecuta nada sin ese paso explícito),
  y el resultado (venta/compra/ajuste registrado, o una consulta de solo
  lectura) se renderiza de forma legible (`ResultView`), no como JSON
  crudo.
- Pantallas tradicionales de respaldo, pulidas para uso con una mano en
  celular: `ProductsPage` (con ajuste de stock inline), `SalesPage`,
  `PurchasesPage`, `CashboxPage` (dashboard de caja/ventas/stock bajo).
- `DocumentsPage`/`DocumentDetailPage`: fotografiar/subir un documento
  (`<input capture="environment">`, reutilizando la validación de
  archivos de la Fase 9), ver en vivo las transiciones de estado
  (`uploaded → processing → needs_review`), revisar y **corregir** los
  datos extraídos antes de confirmar, o rechazar sin registrar nada.
- PWA instalable: `public/manifest.webmanifest`, íconos generados a
  partir del favicon del proyecto, y un Service Worker escrito a mano
  (`public/sw.js`, ~40 líneas) que cachea solo el "shell" de la app
  (stale-while-revalidate) y **nunca intercepta `/api/` ni `/media/`**
  — ver `docs/ARCHITECTURE.md` #3.1 ("no cache de datos de negocio
  sensibles por defecto"). Se registra solo en producción, nunca en
  `npm run dev`.
- 11 tests nuevos con Vitest + Testing Library: el cliente HTTP (adjunta
  headers correctos, reintenta tras refrescar el token, limpia la sesión
  si el refresh también falla, extrae mensajes de error de las distintas
  formas de `ValidationError` de DRF), `AuthContext` (login/logout), y
  el flujo completo de `ChatPage` (proponer → confirmar, proponer →
  cancelar, mensaje no entendido). Sumados a `npm run test` en CI.
- **Bug real encontrado y corregido durante la verificación manual en
  navegador** (no detectable con `curl`, que ignora CORS por completo):
  `django-cors-headers` no incluía `X-Company-Id` en su lista default de
  headers permitidos, así que el navegador bloqueaba en el preflight
  cualquier request autenticada del frontend a un endpoint de negocio.
  Corregido con `CORS_ALLOW_HEADERS` explícito en
  `backend/config/settings.py`.
- Verificado de punta a punta en un navegador real (Chromium headless,
  viewport móvil 390×844, no solo mocks/tests unitarios): registro →
  crear empresa → crear producto → "Vendí 3 cafés a 2500" por chat →
  confirmar → venta reflejada en Ventas y en el dashboard de Caja →
  fotografiar una factura sintética → OCR real (Tesseract) →
  estructuración → revisar/corregir → confirmar → compra registrada,
  sin ningún error de consola del navegador.

### Fase 9 — Captura de documentos y OCR

- Nueva app `documents`: modelos `Document` (`status`:
  `uploaded|processing|needs_review|confirmed|rejected|failed`,
  `document_type_guess`, imagen subida a `_document_upload_path` con
  nombre aleatorio) y `DocumentExtraction` (1-1 con `Document`:
  `raw_ocr_text`, `structured_data` JSONB, `reviewed_by`/`reviewed_at`).
- `OCRProvider` (`documents/ocr_providers.py`): misma arquitectura de
  interfaz + implementaciones que `LLMProvider` — `TesseractOCRProvider`
  (real, local, sin red — nueva decisión documentada como ADR-011: se
  prefiere Tesseract a PaddleOCR/docTR de ADR-005 por ser instalable vía
  `apt`, sin GPU y sin Docker) y `FakeOCRProvider` (tests).
- `documents/structuring.py::estructurar_documento`: reutiliza el mismo
  `LLMProvider` del asistente (Fase 8) para transformar el texto OCR
  crudo en JSON estructurado (proveedor, ítems, total), con la misma
  lógica de parseo/tolerancia de bloques markdown que el Orchestrator
  (extraída a `core/json_utils.py::parse_json_object`, usada ahora por
  ambos).
- Procesamiento asíncrono real con Celery + Redis
  (`documents/tasks.py::procesar_documento`): al subir un documento se
  encola la tarea, que hace `uploaded → processing → needs_review` (o
  `failed` si algo falla), corriendo OCR + estructuración fuera del
  request HTTP. `CELERY_TASK_ALWAYS_EAGER=true` en tests/CI para correr
  la tarea de forma síncrona sin necesitar un broker real. Nuevos
  servicios `redis` y `worker` en `docker-compose.yml`.
- Endpoints: `GET/POST /api/documents/` (listar / subir imagen,
  `multipart/form-data`), `GET /api/documents/<id>/` (detalle +
  extracción), `POST /api/documents/<id>/confirm/` (con los datos
  corregidos por el usuario si hace falta, registra la compra/venta real
  reutilizando `registrar_compra`/`crear_venta` sin duplicar lógica —
  solo procede desde `needs_review`), `POST /api/documents/<id>/reject/`.
  Ver `docs/SECURITY.md` #7: subir/procesar un documento nunca registra
  nada por sí solo, siempre se necesita la confirmación explícita.
- Validación de subida de archivos (`docs/SECURITY.md` #6): whitelist de
  `Content-Type`, tamaño máximo configurable
  (`DOCUMENT_MAX_UPLOAD_SIZE_BYTES`), verificación real de que el
  archivo es una imagen válida (`PIL.Image.verify()`), límite de
  dimensiones, nombre de archivo aleatorio (UUID, no el nombre original
  del usuario) y remoción de metadatos EXIF (`documents/image_utils.py`)
  antes de guardar.
- Aislamiento multiempresa verificado para la nueva app (gate
  obligatorio de `docs/TESTING.md` #2): un usuario no puede listar, ver,
  confirmar ni rechazar documentos de otra empresa (siempre 404, nunca
  403 ni 200 con datos ajenos).
- `Dockerfile`: se agregan los paquetes de sistema `tesseract-ocr` +
  `tesseract-ocr-spa`. CI instala los mismos paquetes vía `apt` para el
  job de backend.
- Tests nuevos (159 en total): validación de archivos subidos,
  `TesseractOCRProviderTests` (OCR real sobre una imagen sintética
  generada en el propio test, no un mock, para probar el proveedor de
  verdad), `estructurar_documento` (respuesta válida del LLM, respuesta
  inválida cae a estructura vacía, ítem sin match de producto queda con
  `product_id` nulo), la tarea de Celery, y la suite de integración de
  documentos (subida → procesamiento → confirmación → stock/caja,
  doble confirmación rechazada, rechazo, aislamiento multiempresa).
- Verificado manualmente de punta a punta con infraestructura real (no
  solo mocks/eager): Redis real, un worker de Celery real corriendo en
  segundo plano, Tesseract real vía `pytesseract` sobre una imagen
  sintética de una "factura", y un servidor local que imita el formato
  de la API de Ollama para la estructuración. Se observaron las
  transiciones de estado asíncronas reales (`uploaded → processing →
  needs_review`), y tras confirmar: la compra quedó registrada
  (`total` correcto), el stock del producto subió de 0 a la cantidad
  comprada, el resumen de caja reflejó el egreso, y el documento quedó
  `confirmed` con `reviewed_by`/`reviewed_at` completos.

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
