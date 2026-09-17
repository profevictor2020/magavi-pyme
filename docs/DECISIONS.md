# MAGAVI — Registro de Decisiones Arquitectónicas (ADR)

Formato breve: Contexto → Decisión → Alternativas consideradas →
Consecuencias. Se agregan entradas nuevas al final; no se editan las
existentes salvo error de hecho (se marca como "Reemplazada por ADR-XXX"
si cambia).

---

## ADR-001 — Backend: Django + DRF (no FastAPI)

**Contexto:** el MVP es, en volumen, mayoritariamente CRUD con reglas de
negocio (productos, ventas, compras, inventario, caja, usuarios/empresas,
auditoría) más un módulo de asistente que consume esos mismos servicios.

**Decisión:** Django + Django REST Framework.

**Alternativas consideradas:** FastAPI (async nativo, más natural para
streaming de LLM y llamadas HTTP a servicios de inferencia).

**Por qué Django y no FastAPI:**
- Multi-tenancy, auth, permisos, migraciones y admin ya vienen resueltos o
  con patrones maduros (`django.contrib.auth` customizado, ORM +
  migraciones versionadas, admin para soporte/depuración interna).
- DRF acelera la construcción de los 8+ módulos CRUD del MVP
  (serializers, viewsets, permisos) más rápido que ensamblar el
  equivalente a mano en FastAPI (que con Pydantic + SQLAlchemy + Alembic +
  un sistema de auth propio termina replicando gran parte de Django de
  todas formas).
- El punto fuerte de FastAPI (async/streaming) no es crítico para el MVP:
  la llamada al LLM/OCR puede ser síncrona desde una vista o, mejor,
  delegarse a Celery (que ya se necesita para OCR de todos modos). No
  hay necesidad de servir miles de conexiones concurrentes en el MVP.
- Django admin resulta muy útil para depuración/soporte temprano sin
  construir herramientas internas ad-hoc.

**Consecuencias:** si más adelante el asistente requiere streaming
token-a-token de baja latencia, se puede exponer esa ruta específica con
Django ASGI (Django 4.2+/5 soporta vistas async) sin migrar todo el
backend, o aislar esa ruta en un servicio pequeño dedicado. No se
considera necesario para el MVP.

---

## ADR-002 — Multi-tenancy: aislamiento por fila (shared schema), no
schema-per-tenant

**Contexto:** los datos de una empresa nunca deben mezclarse con los de
otra; hay que elegir el mecanismo de aislamiento en PostgreSQL.

**Decisión:** una sola base de datos y esquema, con `company_id` en cada
tabla de negocio, reforzado con middleware + manager scoped + tests de
aislamiento obligatorios (detalle en `ARCHITECTURE.md` §4 y
`SECURITY.md` §4).

**Alternativas consideradas:** *schema-per-tenant* (p.ej. `django-tenants`)
o *database-per-tenant*.

**Por qué no schema/database-per-tenant en el MVP:**
- Complejidad operacional significativamente mayor (migraciones por
  schema, conexión dinámica, backups por tenant) sin beneficio claro al
  volumen esperado del MVP (decenas/cientos de PyMEs, no miles de tenants
  con requisitos regulatorios de aislamiento físico).
- El aislamiento por fila, bien probado y con defensa en profundidad
  (middleware + manager + tests + RLS como hardening futuro), es
  suficiente y mucho más rápido de construir y depurar.

**Consecuencias:** si en el futuro un cliente exige aislamiento físico
(p.ej. requisito contractual/regulatorio), se puede migrar empresas
específicas a un esquema o base separada sin rediseñar el modelo de
datos, porque `company_id` ya está presente en todo. Se documenta
Row Level Security de PostgreSQL como hardening de Fase 11, no como
sustituto del diseño anterior.

---

## ADR-003 — El LLM propone intención estructurada; no se acopla a
"function calling" nativo de un proveedor/modelo específico

**Contexto:** distintos modelos open-source difieren en la madurez de su
soporte nativo de "function/tool calling", y el requisito explícito del
proyecto es no depender de un proveedor externo, manteniendo la
posibilidad de cambiar de modelo.

**Decisión:** se define un `IntentSchema` propio (JSON Schema/pydantic),
versionado, con la lista cerrada de operaciones soportadas. Se instruye al
modelo (vía prompt + few-shot) para que responda siempre en ese formato.
El backend valida estrictamente contra el schema antes de mapear a una
llamada del Tool Layer. El LLM **nunca** ejecuta nada directamente ni
recibe acceso a la base de datos.

**Alternativas consideradas:** usar el mecanismo de tool-calling nativo de
un modelo/runtime particular (p.ej. el formato específico de Llama o de
Mistral).

**Por qué no:** acoplarse al formato nativo de un modelo ata la
arquitectura a ese modelo/runtime concreto, dificultando comparar/cambiar
modelos (importante dado que el ecosistema open-source evoluciona rápido)
y complica las pruebas deterministas de Fase 7 (que deliberadamente no
dependen de ningún LLM).

**Consecuencias:** algo de trabajo extra en prompting/parsing propio, pero
máxima portabilidad de modelo y una capa de validación explícita y
auditable, en línea con el requisito de que "el backend controla las
operaciones".

---

## ADR-004 — Motor de inferencia LLM privado: candidatos y runtime

**Contexto:** requisito explícito de no depender de OpenAI/Anthropic/
Gemini en producción; se necesita un modelo con buen soporte de español,
capaz de seguir instrucciones de formato estructurado, con consumo de
recursos razonable para autoalojar.

**Decisión (para evaluar en Fase 8, no cerrada en piedra):** empezar con
**Qwen2.5-7B-Instruct** o **Llama-3.1-8B-Instruct** como candidatos
primarios, servidos vía **Ollama** en desarrollo/MVP (setup simple, API
HTTP compatible con OpenAI) con posibilidad de migrar a **vLLM** si se
necesita más throughput en producción. Ambos modelos: licencia
permisiva, buen desempeño en español, tamaño manejable en una GPU de
gama media (o CPU con cuantización para volúmenes bajos vía
`llama.cpp`/Ollama).

**Alternativas consideradas:** Mistral 7B/Mixtral 8x7B (buen multilingüe,
Mixtral más pesado de autoalojar), Gemma 2 9B (function calling menos
maduro en la práctica), modelos más grandes (mejor calidad pero mayor
costo de infraestructura, no justificado para MVP).

**Por qué no depender del tool-calling nativo del modelo elegido:** ver
ADR-003 — el `IntentSchema` propio hace esta elección reversible con bajo
costo.

**Consecuencias:** se requiere evaluación empírica en Fase 8 (prompt
engineering + pruebas con `IntentSchema`) antes de fijar el modelo
definitivo; se documenta como spike inicial de esa fase, no como
investigación de Fase 0.

---

## ADR-005 — OCR: motor open-source + estructuración vía el mismo LLM
privado (no modelo especializado de layout en el MVP)

**Contexto:** se necesita extraer texto de fotos de boletas/facturas
chilenas (calidad variable) y luego estructurarlo en campos (proveedor,
fecha, ítems, total).

**Decisión:** usar **PaddleOCR** (o **docTR** como alternativa evaluada en
paralelo) para extracción de texto/layout, y reutilizar el **LLM privado**
ya desplegado (ADR-004) para transformar ese texto crudo en el JSON
estructurado de `DocumentExtraction`, reutilizando la misma infraestructura
de prompting/validación que el asistente conversacional.

**Alternativas consideradas:** Tesseract (más simple pero peor en fotos
reales con ruido/inclinación), EasyOCR, modelos "OCR-free" de
comprensión de documentos como Donut o LayoutLMv3 (mejor precisión
potencial en documentos estructurados, pero requieren más esfuerzo de
despliegue/fine-tuning que no se justifica para un MVP).

**Consecuencias:** pipeline más simple de operar (dos servicios: OCR +
LLM, ya necesarios ambos igual) a costa de posible menor precisión en
documentos muy irregulares. Si la calidad resulta insuficiente en
pruebas reales (Fase 9), se revisita con un modelo especializado como
mejora, no como bloqueante del MVP — siempre bajo el principio de que el
usuario revisa y confirma antes de registrar.

---

## ADR-006 — Autenticación: JWT vía `djangorestframework-simplejwt`

**Contexto:** cliente es una SPA/PWA móvil, se necesita autenticación
stateless razonable para múltiples dispositivos.

**Decisión:** JWT de vida corta + refresh token, Argon2 para hash de
contraseña.

**Alternativas consideradas:** sesiones Django tradicionales (menos
natural para un cliente SPA/PWA que puede correr instalado, sin cookies de
sesión de dominio compartido garantizadas).

**Consecuencias:** requiere manejo cuidadoso de expiración/revocación
(blacklist de refresh tokens), documentado en `SECURITY.md`.

---

## ADR-007 — Procesamiento asíncrono: Celery + Redis

**Contexto:** OCR y llamadas a LLM pueden tardar varios segundos; no deben
bloquear el request HTTP ni el hilo principal del backend.

**Decisión:** Celery + Redis (broker) para tareas de OCR/estructuración de
documentos; Redis también disponible para throttling/cache si se
necesita.

**Alternativas consideradas:** procesamiento síncrono directo en la vista
(inaceptable por latencia percibida), colas más pesadas (RabbitMQ, SQS —
innecesarias para el volumen del MVP).

**Consecuencias:** un componente operacional más en `docker-compose`
(`redis`, `worker`), justificado porque ya es necesario para Fase 9 y
puede reutilizarse por cualquier otra tarea diferible futura.

---

## ADR-008 — Monolito modular, no microservicios, para el MVP

**Contexto:** equipo pequeño, MVP con alcance acotado, pero con dos
componentes (LLM, OCR) que por su naturaleza (recursos, runtime distinto a
Python/Django) ya deben correr como procesos separados.

**Decisión:** backend Django como monolito modular (apps con límites
claros y Tool Layer como interfaz interna), con LLM y OCR como servicios
independientes desde el día 1 por necesidad técnica, no como ejercicio de
microservicios.

**Alternativas consideradas:** descomponer también `sales`/`purchases`/etc.
en servicios independientes — descartado por sobreingeniería para el
volumen y el equipo del MVP.

**Consecuencias:** velocidad de desarrollo alta para el MVP; los límites
de módulo (apps Django + Tool Layer) están puestos deliberadamente para
que una futura extracción a servicios (si el crecimiento lo justifica) no
requiera reescribir la lógica de negocio, solo mover su frontera de
despliegue.

---

## ADR-009 — No se permite stock negativo en movimientos de inventario

**Contexto:** `docs/ROADMAP.md` Fase 3/4 exige decidir explícitamente qué
pasa cuando un movimiento (ajuste manual, y más adelante una venta) dejaría
el stock de un producto en negativo, en vez de asumirlo en silencio.

**Decisión:** `ajustar_inventario` (Tool Layer, `inventory/services.py`)
rechaza cualquier movimiento cuyo `balance_after` resultante sea negativo,
lanzando `ValidationError` (HTTP 400 en la API). El cálculo y la
validación ocurren dentro de una transacción con `select_for_update()`
sobre el producto, para evitar condiciones de carrera entre ajustes
concurrentes del mismo producto.

**Alternativas consideradas:** permitir stock negativo (útil para negocios
que venden "a cuenta" antes de reponer) y marcarlo solo como advertencia.

**Por qué no:** para un MVP dirigido a dueños de almacén sin experiencia
en software, un stock negativo silencioso es más confuso que útil, y
esconde errores de captura (cantidad mal escrita, producto equivocado).
Rechazar explícitamente fuerza a corregir el dato en el momento.

**Consecuencias:** si en el futuro se detecta un caso de negocio real que
necesite permitir stock negativo (p.ej. pre-venta), se puede agregar como
una opción explícita por producto o por empresa — no como comportamiento
por defecto. Esta misma regla la heredan `crear_venta` (Fase 4) y
`registrar_compra` (Fase 5), que reutilizan `ajustar_inventario`.

---

## ADR-010 — Proveedor LLM externo (DeepSeek) SOLO para desarrollo y pruebas

**Contexto:** en Fase 8 se necesita validar el Orchestrator (armado de
prompt, parseo de intent, reintentos, defensa contra prompt injection)
contra un modelo real, no solo contra el `FakeLLMProvider` usado en los
tests automáticos. El entorno de desarrollo de esta fase no tiene GPU ni
acceso a Docker Hub (bloqueado por política de red — ver limitación
documentada en la Fase 1), por lo que no es posible autoalojar Ollama/vLLM
ahí. Tampoco es razonable hacerlo en el runner de CI de cada push: bajar
varios GB de pesos de modelo y correr inferencia en CPU en cada commit
haría el pipeline inviablemente lento.

**Decisión:** se agrega `DeepSeekLLMProvider` (`assistant/llm_providers.py`),
un adaptador para la API alojada de DeepSeek (compatible con formato
OpenAI), activable solo con `LLM_PROVIDER=deepseek_dev` +
`DEEPSEEK_API_KEY`. **Nunca es el valor por defecto**: `LLM_PROVIDER`
por defecto sigue siendo `ollama` (self-hosted, ADR-004). El uso de
DeepSeek se limita a pruebas de desarrollo con datos sintéticos, nunca a
producción ni a datos reales de una empresa. Cuando se necesite una
verificación real contra este proveedor, se ejecuta como job manual de
GitHub Actions (`workflow_dispatch`, con la API key como secreto del
repositorio), nunca desde este entorno de desarrollo (que además tiene
bloqueada la salida a `api.deepseek.com` por la misma política de red
que bloquea Docker Hub).

**Por qué esto no contradice el requisito de IA privada:** el requisito
central (`docs/PRODUCT.md` §5, `docs/SECURITY.md`) es que **producción**
no dependa de un proveedor externo — no que el equipo nunca pueda usar
uno para probar código durante el desarrollo. La arquitectura (ADR-003:
contrato de intención propio, no acoplado a un proveedor) es precisamente
lo que hace esto seguro: cambiar de `deepseek_dev` a `ollama` es cambiar
una variable de entorno, no reescribir el Orchestrator.

**Alternativas consideradas:** usar únicamente `FakeLLMProvider` hasta
tener infraestructura real para Ollama (más conservador, pero deja sin
validar cómo se comporta el Orchestrator ante la variabilidad real de un
modelo); instalar un modelo pequeño (~0.5B) nativo sin Docker (descartado
por riesgo de espacio en disco fijo del entorno y porque un modelo tan
chico es poco representativo para evaluar confiabilidad de salida JSON).

**Consecuencias:** queda una dependencia de desarrollo (`requests` +
`DeepSeekLLMProvider`) que no se usa en producción. Se documenta aquí
explícitamente para que nadie la active por defecto sin darse cuenta, y
para que quede claro que es una excepción acotada, no un cambio de
rumbo de ADR-004.

---

## ADR-011 — OCR: Tesseract (no PaddleOCR/docTR) como implementación
concreta del MVP

**Contexto:** ADR-005 dejó abierta la elección entre PaddleOCR y docTR
para el motor de OCR, con Tesseract descartado en ese momento por "peor
en fotos reales con ruido/inclinación". Al implementar la Fase 9 sobre
este entorno (sin GPU, sin acceso a Docker Hub — misma limitación de red
documentada en la Fase 1 y en ADR-010), instalar y mantener PaddleOCR o
docTR (ambos con dependencias pesadas de deep learning, típicamente
distribuidos como imagen Docker o con pesos de varios cientos de MB a
descargar) resulta desproporcionado para un MVP cuyo requisito central es
que el usuario siempre revisa y corrige antes de confirmar (ADR-005,
`docs/SECURITY.md` #7) — es decir, el sistema nunca depende de que el OCR
sea perfecto.

**Decisión:** usar `pytesseract` (wrapper de Tesseract OCR) como
implementación concreta de `OCRProvider` (`documents/ocr_providers.py`,
`TesseractOCRProvider`) para el MVP. Tesseract se instala nativamente vía
`apt` (paquetes `tesseract-ocr` + `tesseract-ocr-spa`), sin Docker, sin
GPU y sin ninguna llamada de red en tiempo de inferencia — cumple el
mismo principio de IA/procesamiento privado que ADR-004, solo que aquí no
hay siquiera una excepción que documentar: es 100% local y offline por
diseño de la propia herramienta.

**Alternativas consideradas:** PaddleOCR y docTR (ADR-005) siguen siendo
la ruta de mejora si la precisión de Tesseract resulta insuficiente en
pruebas con boletas/facturas reales (letra manuscrita, papel arrugado,
mala iluminación); EasyOCR (misma familia de costo/beneficio que
PaddleOCR/docTR, descartado por el mismo motivo).

**Consecuencias:** el pipeline de Fase 9 queda validado extremo a extremo
con OCR real (no mockeado) usando infraestructura mínima. Si en uso real
la tasa de corrección manual por parte de los usuarios resulta muy alta,
se revisita esta decisión reemplazando `TesseractOCRProvider` por un
adaptador `PaddleOCRProvider`/`DocTROCRProvider` que implemente la misma
interfaz `OCRProvider` — el resto del sistema (Celery task, estructuración
vía LLM, flujo de confirmación) no necesita cambiar.

---

## ADR-012 — Stack de frontend para la Fase 10: React Router, CSS a mano,
Context de React, tokens en localStorage, Service Worker escrito a mano

**Contexto:** hasta la Fase 9 el frontend era solo el scaffold de Vite +
React (una pantalla placeholder). La Fase 10 requiere construir la PWA
real completa: pantallas de auth/empresa, el chat como pantalla
principal, las pantallas tradicionales de respaldo (productos, ventas,
compras, documentos, caja) y la instalabilidad (manifest + Service
Worker) — ver `docs/ARCHITECTURE.md` #3.1 y `docs/ROADMAP.md` Fase 10.
Había que decidir varias piezas de stack antes de empezar a programar.

**Decisiones tomadas (todas de bajo riesgo/reversibles, no ameritaban
pausar a discutir con el usuario como sí lo ameritó el proveedor de LLM
en la Fase 8):**

- **Enrutamiento:** `react-router-dom` (estándar de facto, sin
  alternativa mejor para una SPA de este tamaño).
- **Estilos:** CSS a mano (variables CSS en `:root` para colores/espaciado,
  clases utilitarias simples), **no** un framework de componentes
  (Tailwind/MUI/etc.). Mantiene el bundle chico y cada estilo es
  auditable a simple vista, coherente con el resto del proyecto
  (preferir simplicidad y pocas dependencias sobre abstracciones).
- **Estado de sesión/empresa:** dos React Context (`AuthContext`,
  `CompanyContext`) en vez de una librería de estado global — el estado
  compartido real (usuario, empresa activa) es chico y no justifica
  Redux/Zustand/etc.
- **Tokens JWT en `localStorage`** (`api/tokenStore.ts`): más simple de
  implementar que cookies `httpOnly` con el backend actual (que no las
  emite). **Tradeoff aceptado conscientemente:** un XSS en la SPA podría
  robar el token, algo que cookies `httpOnly` mitigarían. Para el MVP,
  con las defensas ya existentes (CSP básica, sin `dangerouslySetInnerHTML`
  en ningún componente, React escapa por defecto), se acepta el riesgo;
  si en producción real se requiere mayor garantía, la migración a
  cookies `httpOnly` + `SameSite` requiere cambios en `accounts/views.py`
  y queda documentada aquí como mejora futura, no como bloqueante del MVP.
- **Empresa activa por request:** en vez de depender del valor guardado
  en `localStorage` en el momento del fetch, cada función de
  `api/endpoints.ts` recibe `companyId` explícito desde
  `CompanyContext`. Se detectó que depender del valor persistido
  introducía una condición de carrera real entre el efecto que persiste
  la selección y el efecto de la página que dispara el fetch (el orden
  de ejecución de `useEffect` entre un componente padre y sus hijos no
  está garantizado a favor del padre) — pasar el id a mano lo evita de
  raíz.
- **Service Worker escrito a mano** (`public/sw.js`), no
  `vite-plugin-pwa`/Workbox: solo cachea el "shell" (HTML/JS/CSS, vía
  stale-while-revalidate para no depender de conocer nombres de archivo
  hasheados de antemano) y **nunca intercepta `/api/` ni `/media/`**, en
  línea con `docs/ARCHITECTURE.md` #3.1 ("no cache de datos de negocio
  sensibles por defecto"). Un archivo de ~40 líneas es más fácil de
  auditar para ese requisito de seguridad que una configuración de
  Workbox con varias estrategias de caché.
- **Cámara:** `<input type="file" accept="image/*" capture="environment">`
  (tal como especifica `docs/ARCHITECTURE.md` #3.1), sin usar
  `MediaDevices.getUserMedia` — más simple, funciona en todos los
  navegadores móviles relevantes, y reutiliza el mismo input de subida
  de archivo ya validado en el backend (Fase 9).
- **Tests:** Vitest + Testing Library para lógica/componentes clave
  (cliente HTTP con refresh de token, `AuthContext`, el flujo completo
  de proponer/confirmar/cancelar del `ChatPage`) — no un framework de
  componentes visuales nuevo, para no sumar otra herramienta al pipeline
  de CI.

**Bug real encontrado durante la verificación manual en navegador (no
detectable con `curl`, que no aplica CORS):** `django-cors-headers` no
incluye `X-Company-Id` en su lista default de headers permitidos, así
que el navegador bloqueaba en el preflight cualquier request autenticada
del frontend a un endpoint de negocio — las pruebas manuales de fases
anteriores usaron siempre `curl`, que ignora CORS por completo, así que
esto nunca se había detectado. Corregido agregando `CORS_ALLOW_HEADERS`
explícito en `backend/config/settings.py` (los headers default de
`corsheaders` más `x-company-id`).

**Consecuencias:** el frontend queda con dependencias mínimas
(`react-router-dom` como única dependencia de producción nueva) y sin
ninguna decisión de este ADR que sea difícil de revertir después si se
justifica (p. ej. migrar a `vite-plugin-pwa` si el Service Worker a mano
se vuelve difícil de mantener, o a cookies `httpOnly` si se necesita
mayor garantía contra XSS).

---

## ADR-013 — PostgreSQL Row Level Security: diferido, no bloqueante
para el MVP

**Contexto:** `docs/SECURITY.md` #4 y `docs/ROADMAP.md` Fase 11 listan
PostgreSQL Row Level Security (RLS) como una segunda capa de aislamiento
multiempresa "opcional (evaluar según tiempo)", independiente de bugs de
aplicación: hoy el aislamiento depende enteramente de que
`CompanyScopedManager`/`get_current_company` se usen correctamente en
cada vista y cada Tool Layer (defensa en una sola capa de código, aunque
con tests de aislamiento obligatorios en cada fase desde la Fase 2).

**Decisión:** no implementar RLS en esta fase. Se evaluó el esfuerzo
real: requeriría (a) una política RLS por tabla de negocio
(`CREATE POLICY ... USING (company_id = current_setting('app.company_id')::int)`),
(b) que cada conexión de Django fije `app.company_id` vía
`SET LOCAL` al inicio de cada request (un middleware o decorator nuevo,
ya que Django no gestiona esto nativamente), (c) verificar que
`psycopg`/el pool de conexiones no reutilice conexiones entre requests
de distintas empresas sin resetear ese valor, y (d) migrar el rol de la
aplicación a uno sin `BYPASSRLS` (el rol por defecto de un superusuario
de desarrollo lo tiene). Ninguno de estos puntos es trivial de hacer
bien, y un RLS mal configurado (p. ej. una política que se olvida en una
tabla nueva) da una falsa sensación de seguridad — potencialmente peor
que no tenerlo, si se asume que "ya está cubierto por RLS" y se relaja
la disciplina de tests de aislamiento por app.

**Por qué esto no debilita la postura de seguridad del MVP:** el
aislamiento por aplicación ya tiene defensa en profundidad real, no una
sola capa: `CompanyScopedManager` falla cerrado (lanza excepción) ante
cualquier query sin `.for_company()`, en vez de devolver todo el dataset
(ver `core/managers.py`); cada fase que agrega un modelo/endpoint nuevo
tiene como gate obligatorio un test de aislamiento cruzado (crear 2
empresas, verificar 404 en listado y en acceso directo por id); y la
Fase 11 sumó una batería consolidada (`core/test_security.py`) que
prueba esto de forma transversal. RLS agregaría una capa extra ante un
bug de aplicación que ningún test detectó — un escenario real pero de
probabilidad baja dado lo anterior, no el vector de riesgo dominante
para un MVP con un puñado de empresas piloto.

**Alternativas consideradas:** implementarlo ahora de todos modos (se
descartó por el costo/riesgo de una implementación apurada, ver arriba);
no mencionarlo en absoluto (se descartó — mejor documentar la decisión
explícitamente que dejarlo como un olvido silencioso).

**Consecuencias:** queda como mejora de hardening documentada, no como
bloqueante. Se revisita si: el número de tablas/empresas crece lo
suficiente como para justificar la inversión, se contrata una auditoría
de seguridad externa que lo pida explícitamente, o se detecta en
producción un bug de aislamiento que RLS hubiera prevenido (en cuyo
caso, además de corregir el bug puntual, se prioriza RLS de inmediato).

---

## ADR-014 — Despliegue: una sola VM Always Free de Oracle Cloud,
self-hosting completo

**Contexto:** con las Fases 0–12 completas, se necesitaba un entorno
real (no local) para demostrar el MVP, sin costo, sin comprometer la
decisión ya tomada de que el LLM y el OCR corren en infraestructura
propia, nunca en un proveedor externo (ver ADR-004, ADR-010, y
`docs/ROADMAP.md` "Qué se necesita para considerar que existe un MVP
demostrable"). Esa restricción descarta a la mayoría de los tiers
gratuitos típicos (Render, Railway, Fly.io): dan ~512MB de RAM en su
capa gratis, insuficiente para correr Ollama con cualquier modelo
razonable.

**Decisión:** desplegar el `docker compose` completo (backend, worker,
Postgres, Redis, Ollama, frontend) en una única VM del tier "Always
Free" de Oracle Cloud (`VM.Standard.A1.Flex`, hasta 4 OCPU / 24GB RAM,
ARM, gratis de forma permanente, no un trial con vencimiento). El
frontend se sirve como build de producción vía NGINX (no el servidor de
desarrollo de Vite), que además hace de reverse proxy hacia el backend
bajo el mismo origen — evitando CORS en producción sin agregar un
servicio nuevo. Ver `docs/DEPLOY.md` para la guía paso a paso y
`docker-compose.prod.yml`/`.env.prod.example` para la configuración.

**Alternativas consideradas:**
- *Render/Railway/Fly.io free tier:* descartado por RAM insuficiente
  para el LLM self-hosted (ver contexto).
- *Usar una API de LLM externa (Groq, Gemini, etc.) para poder usar
  esos free tiers:* descartado — contradice directamente ADR-004/
  ADR-010 y el criterio de aceptación del MVP ("el LLM y el OCR corren
  en infraestructura propia... en el ambiente de demo/producción").
  Queda como opción documentada, no tomada, si en el futuro se
  reevaluara esa restricción explícitamente.
- *Separar el despliegue en varios servicios gratuitos* (frontend en
  Vercel/Cloudflare Pages, backend+DB en Render, LLM en otro lado):
  descartado por complejidad innecesaria para un MVP — más piezas
  gratuitas que coordinar, sin resolver el problema de fondo (dónde
  correr el LLM con RAM suficiente gratis).

**Consecuencias:** sin HTTPS todavía (no hay dominio propio apuntando a
la VM, y Let's Encrypt no emite certificados para IPs desnudas) — queda
documentado como paso pendiente en `docs/DEPLOY.md` §9, aceptable para
una demo/piloto inicial pero no para manejar datos sensibles de
producción real de forma indefinida. Un solo punto de falla (una sola
VM, sin redundancia, sin balanceo de carga) — aceptable para el volumen
de un MVP/piloto, a revisar si el negocio crece más allá de eso. Sin
respaldo automatizado de base de datos todavía (solo manual, ver
`docs/DEPLOY.md` §8).

---

## ADR-015 — Despliegue de demo alternativo: Render + Neon + DeepSeek
(excepción explícita y acotada, sin datos reales)

**Contexto:** al ejecutar ADR-014 en la práctica, la forma
`VM.Standard.A1.Flex` resultó sin capacidad disponible ("Out of
capacity") en la región Always Free de la cuenta (Santiago), tanto en
4 OCPU/24GB como en 2 OCPU/12GB, y la cuenta (recién creada) tampoco
tenía todavía permiso para suscribirse a una región adicional donde
reintentar — una limitación temporal de aprovisionamiento de cuenta,
no del diseño. En vez de bloquear toda demostración del MVP hasta que
esa capacidad se libere, se decidió habilitar un camino de despliegue
alternativo, en paralelo, para tener algo real y navegable mientras
tanto.

**Decisión:** desplegar en Render (backend + frontend, ambos free
tier) usando **Neon** como Postgres externo (gratis, sin fecha de
vencimiento, a diferencia del propio Postgres de Render que expira a
los 30 días) y **DeepSeek** (`LLM_PROVIDER=deepseek_dev`, ya existente
en el código desde ADR-010, antes limitado a desarrollo) como proveedor
de LLM para el asistente. Esto **contradice directamente** ADR-004/
ADR-010 ("nunca un proveedor externo en producción") — se acepta
**únicamente** porque este entorno de Render queda marcado, explícita y
permanentemente, como demo sin datos reales de ninguna pyme (ver
`docs/DEPLOY_RENDER.md`, encabezado). No reemplaza a ADR-014: el camino
de Oracle Cloud (self-hosted, apto para datos reales) sigue siendo el
objetivo cuando la capacidad esté disponible, y ambos despliegues
pueden coexistir mientras tanto — `render.yaml` y
`docker-compose.prod.yml` no se estorban entre sí.

Tampoco hay worker de Celery separado: el free tier de Render no
ofrece un tipo de instancia gratis para "Background Worker" (confirmado
al revisar su pricing — background workers no tienen free tier, incluso
si el tipo de servicio "aparece" disponible). En vez de forzar un
worker pagado solo para esto, se usa `CELERY_TASK_ALWAYS_EAGER=true`
(el mismo mecanismo, sin Redis, que ya usa el job `backend` de CI desde
la Fase 11) — el procesamiento de OCR/documentos corre síncrono dentro
del propio request de subida.

**Por qué Neon y no el Postgres propio de Render:** el Postgres gratis
de Render se borra automáticamente a los 30 días de creado (con 14 días
de gracia) — inviable para algo que se quiere seguir usando como demo
más de un mes sin recrear la base cada vez. Neon no tiene esa fecha de
vencimiento en su tier gratis (sí duerme por inactividad, pero despierta
sola en la siguiente consulta).

**Alternativas consideradas:**
- *Esperar a que se libere capacidad en Oracle Cloud sin tener nada
  desplegado mientras tanto:* descartado — no hay razón para bloquear
  toda demostración por un problema de capacidad ajeno al diseño,
  dado que existe un camino igual de rápido de habilitar y
  perfectamente aceptable para un entorno sin datos reales.
- *Postgres propio de Render en vez de Neon:* descartado por el
  vencimiento a 30 días (ver arriba).
- *Pagar por un Background Worker en Render para mantener Celery+Redis
  igual que en Oracle:* descartado — costo innecesario cuando
  `CELERY_TASK_ALWAYS_EAGER` ya es un mecanismo probado (lo usa CI desde
  la Fase 11) y la demo no tiene el volumen que justificaría procesar
  documentos de forma realmente asíncrona.

**Consecuencias:** dos guías de despliegue conviven (`docs/DEPLOY.md`
para Oracle/self-hosted, `docs/DEPLOY_RENDER.md` para esta demo) — hay
que mantener claro cuál es cada una. El filesystem del backend en
Render es efímero (documentos subidos no persisten entre reinicios/
despliegues) y el servicio duerme tras ~15 min de inactividad (cold
start ~30-50s) — ambos aceptables para una demo, documentados en
`docs/DEPLOY_RENDER.md`, nunca para producción real. Si más adelante
Oracle Cloud da capacidad, ese despliegue pasa a ser el "real" (con
datos reales de pilotos), y este de Render queda como entorno de
demo/pruebas permanente, no se retira.

---

## ADR-016 — Interacción por voz en el chat (Web Speech API del navegador)

**Contexto:** el chat ya permite proponer y confirmar/cancelar
acciones que mutan datos (ventas, compras, ajustes de inventario, alta
de productos) por texto y con botones. El feedback del usuario fue
explícito: para que el asistente se sienta realmente conversacional
("que en verdad se sienta como una IA") y no un formulario disfrazado,
la misma interacción — incluida la confirmación de una mutación —
debe poder hacerse por voz, de punta a punta: el usuario habla, el
sistema responde hablando y, si la acción requiere confirmación, la
pregunta y vuelve a escuchar la respuesta sin que haya que tocar la
pantalla.

**Decisión:** se usa la Web Speech API del navegador, sin backend
propio de voz. Dos piezas independientes (`frontend/src/lib/speech.ts`):

- **Síntesis de voz** (`speechSynthesis`/`SpeechSynthesisUtterance`,
  función `speak()`): corre 100% en el dispositivo, sin red. No es una
  excepción a nada — mismo principio de procesamiento local del resto
  del proyecto.
- **Reconocimiento de voz** (`SpeechRecognition`/
  `webkitSpeechRecognition`, función `listenOnce()`): en la mayoría de
  navegadores (Chrome incluido) el audio capturado se envía al servidor
  del fabricante del navegador para transcribirlo — no hay implementación
  de reconocimiento verdaderamente local y estándar disponible hoy en
  los navegadores objetivo del proyecto. Esto es una **excepción
  documentada y acotada** al mismo principio de IA/procesamiento
  privado de ADR-004, del mismo tipo que la de DeepSeek en ADR-010: se
  acepta porque (a) el MVP en Render (ADR-015) ya está marcado
  explícitamente como demo sin datos reales de ninguna pyme, y (b) usar
  la voz es siempre **opcional** — el botón de micrófono solo aparece
  si el navegador soporta `SpeechRecognition` (`isVoiceInputSupported()`),
  y todo el flujo por texto/botones sigue funcionando exactamente igual
  para quien no lo use. No reemplaza un motor de reconocimiento
  autoalojado (p. ej. Whisper) para producción real con datos reales de
  pymes — eso queda pendiente para cuando ese caso se materialice.

El flujo de confirmación por voz (`ChatPage.tsx`, función
`sendMessage`) es: al recibir una propuesta que requiere confirmación,
el sistema primero **lee la pregunta en voz alta** (`speak()`) y luego
**vuelve a escuchar** (`listenOnce()`) esperando un sí/no — nunca deja
la iniciativa de "acordarse de confirmar" al usuario. La interpretación
de esa respuesta como sí/no (`matchYesNo()`) es **puro matching local de
palabras clave** (nunca se manda al LLM): la garantía de seguridad de
que toda mutación pasa por una confirmación determinística
(`docs/SECURITY.md` #5/#8) no puede depender del juicio de un modelo
sobre si "eso sonó a un sí". Si no se reconoce con claridad un sí/no
(silencio, ambigüedad, error de micrófono), la propuesta queda
pendiente tal cual y se confirma/cancela a mano con los botones — no
hay reintento automático de escucha, para no dejar al usuario atrapado
en un loop.

**Por qué no un backend de voz propio (p. ej. Whisper autoalojado) para
este MVP:** el mismo argumento de costo/beneficio que en ADR-005 para
OCR — instalar y mantener un modelo de reconocimiento de voz (típicamente
con dependencias pesadas y/o GPU) es desproporcionado para validar,
frente a un usuario real, si la interacción por voz completa el
problema que se quiere resolver (dejar de sentirse como un formulario).
Si la voz resulta central para el producto, este es el punto natural
para revisar la excepción y reemplazar el reconocimiento por una
implementación autoalojada.

**Alternativas consideradas:**
- *Solo síntesis de voz (leer resultados), sin reconocimiento:*
  descartado — es exactamente lo que el usuario pidió evitar
  explícitamente ("no quiero que sea... el sistema con voz igual le
  pregunte si desea confirmar o cancelar").
- *Grabar audio y mandarlo a un endpoint propio que llame a un STT
  externo (p. ej. Whisper API):* descartado por ahora — agrega una
  segunda excepción de proveedor externo (además de DeepSeek) por un
  beneficio que la Web Speech API ya cubre gratis para validar el MVP.
- *Interpretar la confirmación por voz con el LLM en vez de matching
  local:* descartado — debilitaría la garantía de confirmación
  determinística que es un requisito de seguridad del proyecto, no solo
  una decisión de UX.

**Consecuencias:** el reconocimiento de voz no funciona en navegadores
sin `SpeechRecognition` (Firefox de escritorio, notablemente) — ahí el
botón de micrófono simplemente no aparece (mejora progresiva, no hay
mensaje de error molesto). La calidad del reconocimiento para español
chileno depende del motor del navegador (`lang: 'es-CL'`), fuera del
control del proyecto. Queda pendiente, si el negocio avanza más allá de
MVP/demo, evaluar un motor de reconocimiento autoalojado antes de usar
voz con datos reales de una pyme.

---

## ADR-017 — Vocabulario aprendido por empresa (grounding, no fine-tuning)

**Contexto:** probando el asistente en vivo, mensajes coloquiales que no
calzan con ninguna frase de ejemplo del `SYSTEM_PROMPT` caen en
"no entendido" aunque el usuario los use con naturalidad (ej. "¿cómo va
el negocio?" en vez de "¿cuánto he vendido?"). Cada vez que esto pasa,
la solución hasta ahora fue que yo revisara el caso reportado y ampliara
el `SYSTEM_PROMPT` a mano con un ejemplo más — funciona, pero el usuario
pidió explícitamente algo más automático: que el propio sistema vaya
"pseudoaprendiendo" la jerga particular de cada pyme a partir de lo que
sus usuarios corrigen o aclaran, sin que eso signifique entrenar (ajustar
pesos de) el modelo — cada pyme tiene su propio lenguaje y no hay razón
para mezclarlo entre empresas ni depender de un ciclo de re-entrenamiento.

**Decisión:** nuevo modelo `LearnedPhrase` (`assistant/models.py`),
con scope de empresa como el resto del sistema (`CompanyScopedManager`):
guarda pares (frase del usuario, intent al que correspondió). Se llena
solo en un caso muy acotado — cuando el mensaje actual contiene una
marca explícita de aclaración ("me refiero a", "quiero decir", "o sea",
etc. — ver `_MARCAS_DE_ACLARACION`) Y el mensaje inmediatamente anterior
del asistente en la misma conversación fue "no entendido". En ese caso
se guarda la frase ORIGINAL que falló (no la aclaración) asociada al
intent que la aclaración terminó resolviendo — la próxima vez que
alguien de esa empresa escriba algo parecido a la frase original, ya no
hace falta que aclare.

Este vocabulario se inyecta como contexto adicional del prompt
(`_construir_contexto_vocabulario`), exactamente el mismo mecanismo de
"grounding" que ya se usa para el catálogo (ver ADR sobre el fix de
stock/precio real en el prompt más arriba en este archivo) — nunca se
reentrena ni se ajusta el modelo, así que sigue siendo el mismo LLM
(intercambiable, ver ADR-003/ADR-010) para todas las empresas; lo único
que cambia por empresa es el contexto adicional que recibe.

**Por qué exigir una marca de aclaración explícita (no aprender de
cualquier mensaje que venga después de un "no entendido"):** sin esa
condición, dos mensajes sin ninguna relación real que por casualidad
quedaran uno después del otro (ej. un "no entendido" seguido de un
mensaje totalmente distinto) se asociarían igual, contaminando el
vocabulario de la empresa con relaciones falsas que después
confundirían al modelo en vez de ayudarlo. Es una heurística simple
(no NLP) a propósito — mismo nivel de complejidad que otras heurísticas
ya usadas en el proyecto (`matchYesNo` en el frontend).

**Alternativas consideradas:**
- *Aprender de CUALQUIER mensaje que resuelva bien después de un "no
  entendido", sin exigir marca de aclaración:* descartado por el riesgo
  de falsos positivos explicado arriba.
- *Fine-tuning real del modelo con las correcciones de cada empresa:*
  descartado — requiere infraestructura de entrenamiento y un proveedor
  dispuesto a hacerlo por empresa (contradice ADR-004/ADR-010, ningún
  proveedor externo en producción), pierde la propiedad de que el
  intent se decide de forma determinística por el Tool Layer (el modelo
  solo propone, nunca ejecuta) y sería mucho más difícil de auditar que
  una tabla de frase→intent en la propia base de datos.
- *Guardar todos los "no entendido" sin distinguir cuáles se aclararon
  después:* es lo que ya hace `Message.structured_intent` — sirve para
  que un humano (yo, o quien administre la empresa) revise el registro
  a mano, pero no resuelve el pedido de que el propio sistema se ajuste
  solo; por eso `LearnedPhrase` es un mecanismo aparte y más acotado.

**Consecuencias:** el vocabulario aprendido es visible/editable solo por
Django admin por ahora (`LearnedPhraseAdmin`) — no hay una pantalla en
la PWA para que el dueño de la pyme lo revise o borre una asociación
errónea; queda pendiente si se vuelve necesario. Una empresa nueva
empieza sin vocabulario aprendido (el prompt es idéntico al de antes de
este ADR) y solo empieza a divergir después de su primera aclaración
explícita — el comportamiento por defecto no cambia para nadie.

---

## ADR-018 — Egresos manuales (`registrar_gasto`) con categorías fijas +
aprendizaje de gastos "otro" (mismo mecanismo que ADR-017)

**Contexto:** `CashMovement` ya tenía un tipo `EXPENSE` (egreso), pero
solo se generaba como efecto de `registrar_compra` (comprarle mercadería
a un proveedor) — no había forma de registrar arriendo, sueldos,
cuentas de servicios básicos, ni ningún otro gasto de la pyme que no
fuera reponer inventario. El usuario pidió esto con categorías simples
("arriendo, sueldos, servicios, otro") pero además que el sistema
"pueda ir aprendiendo si es otro un nuevo gasto que nunca se había
ingresado" — el mismo pedido de fondo que ADR-017 (que el asistente se
sienta flexible y no repita preguntas sobre algo que ya le enseñaron),
aplicado ahora a los gastos en vez de al lenguaje de intents en general.

**Decisión:** nuevo Tool Layer `cashbox/services.py::registrar_gasto`
(company, user, amount, category, description opcional) — crea
directamente un `CashMovement` de tipo `EXPENSE`, sin tocar stock ni
productos (a diferencia de `registrar_compra`). `CashMovement` gana un
campo `category` (choices: `arriendo`, `sueldos`, `servicios`, `otro`;
null para movimientos de venta/compra, que ya se distinguen por
`reference_type`). Nuevo intent `registrar_gasto` en el asistente
(mutante, con confirmación como todo lo demás). El resumen de caja
(`cashbox.obtener_resumen`) no necesitó cambios: ya sumaba por
`type=EXPENSE` sin importar el origen.

Para el "aprendizaje" de gastos "otro": en vez de duplicar la tabla
`LearnedPhrase` de ADR-017 (esa es para frase→intent, esto es
gasto→descripción dentro de un intent ya fijo), se usa la data que ya
existe — los propios `CashMovement` con `category="otro"` de la
empresa — como contexto de grounding
(`_construir_contexto_gastos_otros`, mismo patrón que
`_construir_contexto_catalogo`/`_construir_contexto_vocabulario`): se le
muestran al modelo las descripciones de "otro" que esta empresa ya usó
antes, para que reconozca un gasto recurrente y reutilice la misma
redacción en vez de tratarlo como algo nuevo cada vez. No hace falta
una tabla nueva ni un paso de "aclaración explícita" como en ADR-017,
porque acá no hay ambigüedad de intent que resolver — el usuario ya
dijo "es un gasto" y la única pregunta es cómo se llama, así que
alcanza con mostrarle al modelo el historial real de gastos "otro".

**Por qué categorías fijas (no dejar que el modelo invente categorías
libres):** las categorías alimentan reportes/agrupación más adelante —
un campo `category` con valores arbitrarios generados por el modelo
sería inconsistente entre mensajes parecidos ("pago de luz" vs "cuenta
eléctrica" vs "servicio de electricidad" tratados como 3 categorías
distintas). Un enum cerrado de 4 valores, con "otro" como válvula de
escape para lo que no encaja, es más simple y evita ese problema —
la flexibilidad que pidió el usuario vive en la *descripción* dentro de
"otro", no en inventar categorías nuevas.

**Alternativas consideradas:**
- *Reutilizar LearnedPhrase para esto:* descartado — esa tabla asocia
  una frase completa del usuario a un intent completo; acá el intent ya
  está resuelto (`registrar_gasto`) y lo que varía es un parámetro
  dentro de él. Forzarlo en la misma tabla mezclaría dos conceptos
  distintos sin necesidad.
- *Dejar que el modelo proponga categorías libres:* descartado, ver
  arriba.
- *Exigir que el usuario elija la categoría de una lista en vez de que
  el modelo la infiera del texto:* descartado por ahora — contradice el
  pedido explícito de que el lenguaje sea flexible; el modelo ya infiere
  categorías análogas en otros intents (ver `ajustar_inventario`
  infiriendo el motivo).

**Consecuencias:** por ahora `registrar_gasto` solo se puede invocar
desde el chat (no hay una pantalla dedicada en la PWA ni un endpoint
HTTP tradicional) — igual que con `LearnedPhrase`/ADR-017, el
Tool Layer queda listo para que un futuro `CashboxViewSet` lo reutilice
sin cambios si se agrega una pantalla de "Registrar gasto" más
adelante.

---

## ADR-019 — `registrar_gasto` necesitaba su contraparte de lectura y
corrección (`consultar_gastos`/`actualizar_gasto`)

**Contexto:** al probar ADR-018 en vivo, "muéstrame los gastos que
llevamos a la fecha" cayó en `no_entendido` — el propio modelo lo
explicó bien: existía una acción para *registrar* un gasto, pero
ninguna para *consultarlos*. La pregunta de seguimiento del usuario fue
más general y queda como principio para el resto del proyecto:
**"siempre debemos considerar todo esto cada vez que agregamos algo a
la base de datos"** — o sea, no basta con la operación de escritura;
antes de dar una funcionalidad por completa hay que preguntarse cómo se
consulta lo que se guardó y cómo se corrige si alguien se equivocó al
ingresarlo. `registrar_gasto` se había construido solo con la mitad de
ese ciclo.

**Decisión:** dos intents nuevos, mismo patrón de Tool Layer que el
resto del proyecto:
- `consultar_gastos` (solo lectura): lista los egresos manuales de la
  empresa, más recientes primero — nunca incluye compras de inventario
  ni ingresos de ventas, esos son otro concepto con su propio registro.
- `actualizar_gasto` (mutante, con confirmación): corrige monto,
  categoría o descripción de un gasto manual ya registrado. Rechaza
  explícitamente corregir un `CashMovement` generado automáticamente
  por una venta o compra (`reference_type` distinto de `MANUAL`) — esos
  no se "corrigen" acá, se corrigen anulando/rehaciendo esa venta o
  compra, que es su propio flujo con su propia integridad (stock,
  totales, etc.).

Para que `actualizar_gasto` pueda identificar A CUÁL gasto se refiere
el usuario sin que este tenga que decir un ID que nunca ve en pantalla,
se generalizó el contexto de grounding de ADR-018
(`_construir_contexto_gastos_otros`, que solo mostraba descripciones de
categoría "otro") a `_construir_contexto_gastos_recientes`: ahora
incluye TODOS los gastos manuales recientes de la empresa con su
`cash_movement_id`, no solo los "otro" — sirve para las dos cosas a la
vez (reconocer un "otro" recurrente Y resolver a qué gasto corregir),
con un solo contexto en el prompt en vez de dos parecidos.

**Por qué revalidar en el Tool Layer que el movimiento sea manual (no
solo confiar en que el LLM nunca proponga corregir una venta/compra):**
mismo principio que el resto del proyecto — el LLM propone, pero el
Tool Layer es la única fuente de verdad de si una operación es válida
(ver `docs/ARCHITECTURE.md` #3.4). Un mensaje ambiguo o un intento
malicioso ("corrige el monto de mi última venta a 1") no debe poder
alterar plata de una venta real solo porque pasó por `actualizar_gasto`
con el `cash_movement_id` de esa venta.

**Alternativas consideradas:**
- *Dejar `_construir_contexto_gastos_otros` como estaba y agregar un
  contexto nuevo aparte solo para `actualizar_gasto`:* descartado —
  hubiera mandado dos listas parecidas (una con solo "otro", otra con
  todos) en el mismo prompt, gastando tokens para decir casi lo mismo
  dos veces.
- *Permitir corregir cualquier CashMovement, incluidos los de
  venta/compra:* descartado, ver el párrafo de arriba — esos tienen su
  propio ciclo de vida y corregirlos "a mano" rompería la integridad de
  stock/totales que ya mantienen `crear_venta`/`registrar_compra`.

**Consecuencias:** ninguna migración nueva (ambos intents reutilizan el
`CashMovement`/`category` de ADR-018). El mismo principio de esta ADR
— pensar consulta y corrección junto con cada escritura nueva — queda
como lista de verificación implícita para cualquier entidad nueva que
se agregue al asistente de acá en adelante, no solo para gastos.

---

## ADR-020 — Memoria conversacional real (historial de mensajes en el prompt)

**Contexto:** probando en vivo, después de listar los gastos del mes
("Servicios: $18.500..."), la pregunta de seguimiento "¿de qué es este
gasto?" cayó en `no_entendido` — el propio modelo lo explicó: no existe
una acción para consultar el detalle de un gasto puntual. Pero el
problema real era más de fondo, y el usuario lo nombró directamente:
**"no estamos construyendo una secuencia lógica de conversación"**.
Revisando `interpretar_y_proponer`, era literal: cada mensaje se le
mandaba al LLM solo con contexto de sistema (catálogo, vocabulario,
gastos) y el mensaje actual — nunca los mensajes anteriores de la
misma conversación. El modelo no tenía forma de saber que "este gasto"
se refería al único ítem que se acababa de listar, porque nunca vio
ese dato.

**Decisión:** `interpretar_y_proponer` ahora arma el prompt con turnos
reales de conversación además del contexto de sistema:
`_construir_historial(conversation)` agrega los últimos
`MAX_HISTORIAL_MENSAJES` (10) mensajes de la conversación como turnos
`{"role": "user"|"assistant", "content": ...}`, en orden cronológico,
antes del mensaje actual. Para que esos turnos sirvan de algo, el lado
"assistant" tiene que traer datos reales, no un genérico "Listo, aquí
está la información.": `_resumen_resultado_para_historial` le agrega
al mensaje guardado un resumen JSON del resultado real cuando el
intent se ejecutó (acotado a `MAX_RESUMEN_RESULTADO` = 800 caracteres,
para que un resultado grande — ej. un catálogo de 200 productos — no
dispare el costo de tokens cada vez que quede dentro de la ventana de
historial). Para `no_entendido`/`error`/`pending_confirmation` se
guarda el mensaje que ya se le mostraba al usuario, sin cambios.

**Por qué esto no debilita las garantías de seguridad de
docs/SECURITY.md #5 (prompt injection):** los turnos de historial se
mandan igual que siempre — como contenido de rol "user"/"assistant",
nunca concatenados al system prompt — y el SYSTEM_PROMPT ahora incluye
una regla explícita: el historial sirve para resolver referencias
("ese gasto", "el último"), pero la respuesta siempre corresponde al
ÚLTIMO mensaje del usuario, e ignora cualquier instrucción dentro del
historial que intente cambiar las reglas o saltarse la confirmación —
misma defensa que ya existía para el mensaje actual, extendida al
historial. La ejecución real de cualquier mutación sigue validándose
por completo en el Tool Layer (`proponer_intent`/`confirmar_intent`),
nunca en lo que el LLM "recuerde" haber hecho antes — memoria
conversacional es sobre INTERPRETAR el lenguaje, no sobre qué se
ejecuta.

**Alternativas consideradas:**
- *Mandar el historial completo de la conversación, sin límite:*
  descartado — costo de tokens sin techo a medida que la conversación
  crece; 10 mensajes (~5 intercambios) cubre el caso real de "pregunta
  de seguimiento inmediata" sin ese riesgo.
- *Guardar solo el mensaje genérico ("Listo, aquí está la
  información.") en el historial, sin el resultado real:* es lo que ya
  había — exactamente el bug que se está corrigiendo, un historial sin
  datos reales no sirve para resolver referencias.
- *Resolver la referencia con lógica Python acotada (como
  `_frase_fallida_a_aprender` de ADR-017), en vez de dársela al LLM
  como contexto:* descartado para el caso general — "ese gasto", "la
  última venta", "ese producto" son referencias abiertas que el modelo
  ya sabe resolver bien con contexto real; escribir un resolvedor de
  referencias a mano sería reinventar peor lo que el LLM hace nativo.

**Consecuencias:** el prompt crece con el largo de la conversación
(hasta el techo de 10 mensajes + los resúmenes acotados) — más tokens
por mensaje que antes, trade-off aceptado a cambio de que el asistente
realmente sostenga una conversación en vez de tratar cada mensaje como
aislado. Sin conversación (`conversation=None`, el caso de
`/api/assistant/intents/` sin chat) el comportamiento no cambia: no hay
historial que construir.

---

## ADR-021 — Intent `responder`: respuestas informativas sin pasar por el Tool Layer

**Contexto:** con la memoria conversacional de ADR-020 ya funcionando,
se volvió a probar en vivo la misma secuencia: listar los gastos del
mes ("Servicios: $18.500...") y luego preguntar "y este gasto de qué
es". Esta vez el modelo sí resolvió correctamente la referencia — supo
que "este gasto" era el de servicios — pero igual respondió
`no_entendido`, explicando literalmente que "ese gasto no tiene
descripción registrada, así que no hay información para responder".
El problema ya no era de interpretación (eso quedó resuelto), sino de
diseño: `interpretar_y_proponer` solo sabe producir dos tipos de
resultado — una acción del Tool Layer (`proponer_intent`, mutación o
consulta) o `no_entendido`. No existe una tercera opción para "ya sé
la respuesta, pero no es el resultado de ejecutar nada nuevo".

**Decisión:** se agrega `responder` como un intent más en el
`SYSTEM_PROMPT`, pero de una naturaleza distinta a todos los demás:
`{"intent": "responder", "parameters": {"respuesta": "<texto>"}}` es
una respuesta puramente informativa que el modelo arma a partir de lo
que ya tiene — catálogo, contexto de vocabulario/gastos recientes, o
el historial de la propia conversación — sin ejecutar ninguna acción
nueva. En `interpretar_y_proponer`, este intent se maneja con una
rama propia ANTES de `proponer_intent`: nunca toca el Tool Layer, no
crea `PendingAction`, no lee ni escribe nada en la base de datos más
allá de guardar los mensajes de la conversación como siempre. El
resultado queda como `{"status": "answered", "message": ...}`, un
tercer status junto a `no_entendido`/`error`/`executed`/
`pending_confirmation` que el frontend muestra igual que
`no_entendido` (burbuja de texto simple, con lectura en voz alta si
el mensaje vino por micrófono).

El riesgo obvio de este diseño es que el modelo "invente" un dato de
negocio (un monto, un stock, una fecha) en vez de decir que no lo
sabe. Se mitiga solo con la instrucción del prompt, no con validación
de código — porque no hay Tool Layer que valide un texto libre —:
`responder` se documenta explícitamente como "solo cuando la pregunta
YA se puede responder con datos reales que ya tienes... NUNCA inventes
un dato que no esté realmente en el catálogo/contexto/historial", y la
regla de `no_entendido` se amplía para cubrir el caso "la respuesta
requeriría adivinar o no tienes el dato real". Es la misma estrategia
de "grounding" que ya se usa para el resto de los intents (dar
contexto real en vez de dejar que el modelo adivine), aplicada ahora
también a cuándo el modelo tiene permiso de responder directo.

**Por qué esto no compromete la integridad de los datos de negocio:**
`responder` nunca puede mutar nada — no pasa por `proponer_intent`, así
que no existe camino para que una alucinación del modelo se convierta
en una escritura real. En el peor caso, el usuario recibe una
respuesta de texto incorrecta y puede corregir al asistente en el
siguiente turno (que sí queda grounded en el historial, ver ADR-020).
Es un riesgo estrictamente menor al que ya existía: un `no_entendido`
mal explicado también podía contener una afirmación equivocada del
modelo sobre por qué no entendió.

**Alternativas consideradas:**
- *Ampliar `no_entendido` para que devuelva directamente la respuesta
  cuando el modelo "sabe" pero no hay acción:* confunde dos casos con
  semántica de UI distinta — `no_entendido` implica "esto no se
  entendió, aclara"; `responder` implica "aquí está la respuesta". El
  frontend y el usuario necesitan poder distinguirlos a futuro (por
  ejemplo, si se quisiera loguear tasas de `no_entendido` como métrica
  de calidad, mezclar los dos la ensuciaría).
- *Crear un intent de Tool Layer `consultar_detalle_gasto` (u otro
  específico) en vez de una respuesta genérica:* resuelve el caso
  puntual de gastos, pero no generaliza — cualquier pregunta de
  seguimiento sobre datos ya mostrados ("¿y esa venta a qué hora fue?",
  "¿ese producto en qué categoría está?") necesitaría su propio intent
  nuevo. `responder` cubre la clase completa de "pregunta de
  seguimiento sobre datos que ya están en contexto/historial" sin
  multiplicar intents de un solo uso.
- *Dejar que el frontend arme la respuesta localmente a partir del
  historial, sin ida y vuelta al LLM:* descartado — requeriría
  reimplementar en el cliente la misma resolución de referencias en
  lenguaje natural que el LLM ya hace bien, duplicando lógica y
  perdiendo la ventaja de que todo el entendimiento del lenguaje vive
  en un solo lugar (`orchestrator.py`).

**Consecuencias:** un tercer status (`answered`) se suma a la API de
`/api/assistant/chat/` — cualquier cliente nuevo del endpoint debe
tratarlo igual que `no_entendido`/`error` (texto simple, sin acción
pendiente). No hay migración de base de datos ni cambios al Tool
Layer: es puramente una rama nueva en el orquestador y en el prompt.

**Addendum (mismo día):** probando en vivo, "hay otro gasto más
asociado" (con un solo gasto en el contexto) seguido de "pero ese
gasto ya me lo dijiste, hay uno distinto" volvió a caer en
`no_entendido` — pese a que el `motivo` que el modelo devolvió ya
contenía la respuesta completa ("Solo hay un gasto registrado...no
existe otro distinto"). La rama de código funcionaba bien; el problema
era que el SYSTEM_PROMPT solo ejemplificaba `responder` con respuestas
POSITIVAS (explicar un dato que sí existe), así que el modelo no
generalizó a respuestas NEGATIVAS ("no, no hay otro"). Se amplió la
descripción de `responder` para cubrir explícitamente ese caso —
"si puedes explicar con certeza por qué algo no existe/no aplica,
usando datos reales, eso es responder" — y se reforzó la regla de
`no_entendido`: es solo para cuando de verdad falta información, nunca
para cuando el modelo ya tiene la respuesta (incluida una respuesta
"no"). Sin cambios de código ni de la API — puramente una aclaración
del prompt.

---

## ADR-022 — Consultas históricas por período (mes/año/total/rango)

**Contexto:** probando en vivo, el usuario notó que "qué gastos
tenemos este mes" en realidad no filtraba por mes — `consultar_gastos`
solo traía los últimos N gastos manuales, sin ningún filtro de fecha
(funcionaba "por casualidad" mientras todos los gastos de prueba eran
del mismo día). Y "pero en total cuánto llevo vendido" cayó en
`no_entendido`: `consultar_ventas` solo sabe responder hoy/esta
semana, no tiene noción de "total" ni de ningún otro período. El
usuario lo resumió directo: "hay que considerar que sea capaz de
responder por año, rango, mes, etc." — un problema de fondo (falta de
soporte histórico), no un intent puntual que faltara.

**Decisión:** se agrega `core.dates.resolve_period_range(period,
date_from, date_to)`, una sola función que resuelve cualquier consulta
histórica a un rango `(inicio, fin)` en hora local:
- `period` con nombre — "hoy"/"semana"/"mes"/"anio"/"total" — se
  calcula ENTERAMENTE en el servidor (mismo principio que
  `today_and_week_start` ya usaba para "hoy"/"semana"): el modelo no
  necesita saber la fecha de hoy para pedir "este mes" o "este año",
  solo manda el nombre del período.
- `date_from`/`date_to` (fechas explícitas AAAA-MM-DD) cubren
  cualquier otro caso — "gastos de agosto", "ventas del 1 al 15" — y
  tienen prioridad sobre `period` si se dan ambos. Para que el modelo
  pueda calcular estas fechas (necesita saber a qué año se refiere
  "agosto"), se agrega `_construir_contexto_fecha()`: un mensaje de
  sistema más con la fecha/hora actual, mismo mecanismo de grounding
  que ya existía para el catálogo — nunca se le pide al modelo que
  adivine la fecha de hoy.
- Sin `period` ni fechas, el comportamiento no cambia respecto a antes
  de esta ADR: `consultar_gastos` sigue sin filtrar por fecha (trae el
  histórico reciente), y se agrega `consultar_ventas_periodo` — un
  intent NUEVO, separado de `consultar_ventas` — que sin argumentos
  equivale a `period="total"` (todo el histórico de ventas).

`consultar_ventas_periodo` es un intent aparte en vez de agregarle
parámetros a `consultar_ventas` porque `consultar_ventas` tiene otros
consumidores (`GET /api/sales/summary/`, `cashbox.obtener_resumen`)
que dependen de su forma fija `{today, week}` — cambiarla habría sido
un cambio incompatible sin necesidad. Mismo patrón ya usado para
`consultar_ventas_producto` (Fase 8) cuando `consultar_ventas` no
alcanzaba para un caso distinto.

**Por qué el modelo no calcula "este mes" por su cuenta:** aunque
ahora tiene la fecha de hoy en contexto, `period="mes"`/"anio"/"semana"
siguen resolviéndose en el servidor, no calculando `date_from`/
`date_to` a mano — menos superficie de error (el modelo podría
calcular mal el primer día del mes, o el año en un cambio de año) y
menos tokens que gastar en la explicación. La fecha de hoy en contexto
solo es necesaria para el caso que de verdad no tiene un atajo con
nombre: un mes o rango específico que no es "este".

**Alternativas consideradas:**
- *Cambiar la forma de retorno de `consultar_gastos` a un objeto
  `{period, expenses, total}` en vez de mantenerla como lista:* se
  descartó — habría roto `isExpenseList`/`ResultView`/`speech.ts` sin
  necesidad real (el total ya se calcula solo en el frontend a partir
  de la lista, ver `describeResultForSpeech`); mejor mantener la forma
  de salida estable y agregar el filtrado como parámetros de entrada.
- *Que el modelo calcule siempre `date_from`/`date_to`, sin `period`
  con nombre:* descartado — obliga al modelo a hacer aritmética de
  fechas para el caso más común ("este mes", "este año"), con más
  superficie de error que decirle el nombre del período y dejar que el
  servidor lo resuelva.

**Consecuencias:** `consultar_gastos` ahora acepta `period`/
`date_from`/`date_to` (todos opcionales, retrocompatible); su `limit`
por defecto subió de 50 a 200 porque ya no hay que confiar en "los
últimos 50" para cubrir accidentalmente un período. Nuevo intent
`consultar_ventas_periodo` y nueva forma de resultado
`SalesPeriodTotalLike` en el frontend (`isSalesPeriodTotal`,
`periodLabel`). Todo mensaje al LLM ahora incluye la fecha/hora actual
como contexto de sistema adicional — mismo principio de grounding que
ya se aplicaba al catálogo, vocabulario y gastos recientes, nunca
concatenado al mensaje del usuario (no cambia la defensa de
docs/SECURITY.md #5).

---

## ADR-023 — Intent `asesoria`: sugerencias de negocio grounded en datos reales

**Contexto:** probando en vivo, después de ver el ranking de productos
más vendidos, el usuario pidió "dame alguna sugerencia para alguna
estrategia de marketing para poder vender los otros productos" — cayó
en `no_entendido`, correctamente: el asistente solo sabe traducir
mensajes a acciones sobre datos (ventas, gastos, inventario), nunca dar
consejos abiertos. Antes de implementar nada se le preguntó
explícitamente al usuario si quería expandir el alcance del asistente
para cubrir este tipo de pregunta — no es un bug, es una decisión de
producto — y la respuesta fue sí, con una condición explícita: que la
sugerencia use datos reales del negocio (ventas, no solo el catálogo),
no una respuesta genérica de marketing sin relación con la pyme real.

**Decisión:** se agrega `asesoria`, un intent nuevo con la misma
mecánica que `responder` (ADR-021) — no pasa por `proponer_intent`/el
Tool Layer, no crea `PendingAction`, resultado `{"status": "advised",
"message": ...}` — pero con una diferencia central en lo que se le
permite decir: `responder` nunca inventa nada (solo declara hechos ya
verificados); `asesoria` SÍ puede proponer ideas creativas (eso es
inherente a una sugerencia de marketing), pero tiene que basarlas en
datos reales de la empresa, nunca en cifras o hechos de negocio
inventados. Para que esas ideas sean concretas y no genéricas, se
agrega `_construir_contexto_ventas_resumen`: un ranking de productos
más vendidos (reutilizando `sales.services.productos_mas_vendidos`)
que se manda como contexto de sistema en CADA mensaje, igual que el
catálogo — así el modelo puede identificar qué productos del catálogo
no aparecen en el ranking (sin ventas) y sugerir algo específico (ej.
un combo con el producto más vendido) desde el primer mensaje, sin
depender de que el usuario haya pedido el ranking justo antes (aunque
si lo pidió, ADR-020 ya lo deja en el historial igual).

El intent está acotado explícitamente en el `SYSTEM_PROMPT` a consejos
de negocio de ESTA pyme (ventas, marketing, gastos, inventario) — una
pregunta sin relación con gestionar o hacer crecer el negocio (ej. una
tarea personal) sigue cayendo en `no_entendido`, para que MAGAVI no se
convierta en un chatbot genérico.

**Por qué no reutilizar `responder` para esto:** aunque el mecanismo de
ejecución es idéntico, la semántica es distinta y vale la pena
distinguirla — `responder` es una afirmación verificable ("ese gasto
no tiene descripción"); `asesoria` es una opinión/recomendación
("podrías intentar X"). Mezclarlas en un solo intent haría más difícil
razonar sobre la regla de "nunca inventar" (que aplica distinto a cada
una) y sobre cualquier métrica futura de calidad de respuestas. Se
agrega un status HTTP distinto (`"advised"` vs `"answered"`) por la
misma razón, aunque hoy el frontend los trate igual (texto simple +
voz) — deja la puerta abierta a distinguirlos visualmente más adelante
sin otro cambio de API.

**Alternativas consideradas:**
- *No implementar nada, dejar `no_entendido` para este tipo de
  pregunta:* era la opción por defecto — se descartó porque el usuario
  pidió explícitamente la capacidad, con la condición de que use datos
  reales.
- *Sugerencias genéricas sin cruzar con los datos del negocio:* el
  usuario la rechazó explícitamente a favor de la opción con datos
  reales — una sugerencia sin contexto real ("publica en redes
  sociales") es genérica y poco útil para una pyme específica.
- *Convertir MAGAVI en un asistente de negocio de propósito general
  (sin acotar el alcance a consejos de esta pyme):* descartado — se
  agregó la restricción explícita en el prompt para que el asistente
  seguiga siendo una herramienta de gestión, no un chatbot genérico que
  responda cualquier cosa.

**Consecuencias:** un cuarto status (`"advised"`) se suma a la API de
`/api/assistant/chat/`, tratado igual que `no_entendido`/`error`/
`answered` por cualquier cliente (texto simple, sin acción pendiente).
Cada mensaje al LLM ahora también incluye el ranking de ventas como
contexto de sistema (cuando hay ventas registradas) — mismo trade-off
de tokens que los demás contextos de grounding, aceptado por la misma
razón: sin datos reales, la funcionalidad no cumple lo que el usuario
pidió. Sin cambios de base de datos ni del Tool Layer.

---

## ADR-024 — Cantidades en el contexto del LLM: enteras o con decimales según la unidad

**Contexto:** probando `asesoria` (ADR-023) en vivo, la sugerencia de
marketing decía "los lápices de colores han vendido 5.000 unidades
frente a las 10.000 de la regla" — el usuario lo notó: "las unidades
las trata como flotante, debería saber cuándo es flotante según la
unidad de medida, kgs, grs, litros, etc." La causa: `current_stock` y
`quantity` se guardan con 3 decimales (`Product.current_stock`,
soportan kg/lt fraccionarios), así que un producto vendido por
"unidad" con 10 unidades vendidas en realidad es `Decimal("10.000")`
en la base de datos. El frontend ya recorta esos ceros de más para
mostrar resultados estructurados (`formatQuantity` en
`lib/format.ts`), pero el contexto que se le arma al LLM
(`_construir_contexto_catalogo`, `_construir_contexto_ventas_resumen`)
interpolaba el Decimal crudo — y una respuesta de texto libre
(`responder`/`asesoria`) simplemente repite lo que se le dio, sin
ningún recorte.

**Decisión:** se agrega `catalog.models.formatear_cantidad(cantidad,
unit)`: para `unit="unidad"` siempre redondea a entero (nunca tiene
sentido vender "3.5 unidades", así que ni vale la pena mostrar
decimales aunque el dato los traiga); para `unit` en `kg`/`lt`
preserva decimales reales, solo recorta los ceros de más (mismo
resultado que `formatQuantity` del frontend, pero explícito por
unidad en vez de "cualquier entero se ve como entero"). Se usa en los
dos contextos que ya mandan cantidades al LLM
(`_construir_contexto_catalogo` para stock,
`_construir_contexto_ventas_resumen` para unidades vendidas) — para el
segundo, se agregó `unit` al diccionario que devuelve
`sales.services.productos_mas_vendidos` (antes solo traía
`product_id`/`product_name`/`quantity`/`total`), reutilizando el mismo
`.values()` que ya hace join con `Product` sin costo extra de consulta.

**Por qué no bastaba con lo que ya hacía el frontend:** `formatQuantity`
del frontend es "cualquier entero se ve sin decimales, cualquier
fracción real conserva sus decimales" — funciona bien porque nunca le
importa CUÁL es la unidad, solo si el valor de por sí es entero o no.
Eso es correcto para mostrar en pantalla. Pero el LLM no solo muestra
el dato: lo USA para razonar y redactar texto libre, y ahí sí importa
la semántica — "10 unidades" es un conteo, nunca debería llevar
decimales aunque el valor almacenado fuera fraccionario por error;
"2.5 kg" si es genuinamente fraccionario. Formatear por unidad en el
backend, antes de que el dato llegue al prompt, es más robusto que
confiar en que el LLM infiera solo la diferencia.

**Alternativas consideradas:**
- *Cambiar `current_stock`/`quantity` a un tipo entero cuando
  `unit="unidad"`:* descartado — requeriría una migración condicional
  por fila y complicaría el modelo sin necesidad; el dato real
  (siempre un entero para "unidad" en la práctica) no cambia, solo
  cómo se le muestra al LLM.
- *Dejar que el LLM infiera "no muestres decimales para conteos
  enteros" solo con una instrucción en el `SYSTEM_PROMPT`, sin cambiar
  el dato:* menos confiable — ya se vio en vivo que el modelo repite
  literalmente lo que se le da en el contexto; es más robusto no
  dejarle la oportunidad de copiar el ".000".

**Consecuencias:** `sales.services.productos_mas_vendidos` ahora
incluye `unit` en cada fila (cambio aditivo, no rompe a quien ya
consumía `product_id`/`product_name`/`quantity`/`total`). Sin cambios
de base de datos, de la API pública del asistente, ni del frontend —
`formatQuantity` ya hacía lo correcto para las formas estructuradas
que muestra en pantalla; el fix es enteramente del lado del contexto
que arma el backend para el LLM.

---

## ADR-025 — "Avísame cuando..." se traduce al mínimo de stock bajo existente

**Contexto:** probando en vivo, "hazme un recuerdo cuando lleguen a 5
de que tengo que comprar reponer reglas" cayó en `no_entendido`,
explicando que "el sistema no tiene una acción para crear
recordatorios o alertas personalizadas". Es cierto que no existe un
sistema de notificaciones push — pero el sistema SÍ tiene exactamente
el mecanismo que el usuario pedía: `Product.low_stock_threshold`, ya
editable vía `actualizar_producto`, y `consultar_stock_bajo`, que lista
los productos en o bajo ese mínimo. El modelo no hizo la conexión
porque el `SYSTEM_PROMPT` solo describía `low_stock_threshold` como
"mínimo de stock bajo" en abstracto, sin ningún ejemplo que lo
relacionara con el lenguaje natural de "avisar"/"recordar" cuando el
stock baja — el mismo patrón de gap ya visto en ADR-021/ADR-023: la
capacidad existe, pero el prompt no le enseña al modelo a reconocerla
en esa frase concreta.

**Decisión:** se amplía la descripción de `actualizar_producto` en el
`SYSTEM_PROMPT` con el mapeo explícito: "avísame/recuérdame/dime
cuando el stock de X llegue a N" → `actualizar_producto` con
`low_stock_threshold=N` (mismo manejo de valor final/relativo que ya
tenía el precio), y una instrucción explícita de NO usar `no_entendido`
para este caso diciendo que "no hay forma de crear recordatorios" — el
mínimo de stock bajo ES esa forma en este sistema, aunque no envíe una
notificación proactiva (el producto se marca "stock bajo" y aparece la
próxima vez que se consulta, no al momento). Se agrega también
`mínimo de stock bajo actual` a `_construir_contexto_catalogo` (mismo
grounding que ya tenía el precio) para que un cambio relativo ("sube
el mínimo de X en 2") también funcione. Por último, se agrega
`low_stock_threshold` a la forma `ProductLike` del frontend
(`ResultView`/`describeResultForSpeech`, mostrado solo si es mayor a
0): antes de esto, aunque el backend ya devolvía el campo completo
(`ProductSerializer` lo incluye desde siempre), la confirmación visual
después de "avísame cuando..." no mostraba qué umbral quedó
configurado — el usuario no tenía forma de verificar que su pedido se
haya interpretado bien.

**Por qué no crear un intent nuevo tipo "crear_recordatorio":**
hubiera sido una funcionalidad completamente nueva (persistencia de
recordatorios, quizás notificaciones) para resolver algo que el
sistema ya resuelve con el dato que tiene — habría sido trabajo
redundante y una superficie más para mantener, cuando el gap real era
solo de reconocimiento del lenguaje.

**Consecuencias:** ningún cambio de base de datos ni de la API del
Tool Layer — el campo, el intent y el endpoint ya existían. Cambios
puramente de prompt (nuevo ejemplo + contexto de catálogo ampliado) y
de presentación en el frontend (mostrar un campo que el backend ya
devolvía). Sigue siendo honesto sobre la limitación real: no hay
notificación proactiva, solo un estado consultable.

---

## ADR-026 — Intent `consultar_detalle_ventas`: el detalle por venta, no solo el total

**Contexto:** probando en vivo, después de ver "Este mes: $11.400 (3
ventas)" (de `consultar_ventas_periodo`), "detállame esas ventas" cayó
en `no_entendido` — el propio motivo lo explicó bien: "no tengo el
detalle de ventas individuales... solo el total y la cantidad...
necesitaría ejecutar una consulta que entregue el listado de ventas,
pero no existe un intent para listar ventas una por una". A diferencia
de ADR-025 (donde la capacidad ya existía y solo faltaba el
reconocimiento en el prompt), acá el diagnóstico del propio modelo era
correcto: el gap era real. `consultar_ventas`/`consultar_ventas_periodo`
solo agregan (`Sum`/`Count`); no existía ningún intent que devolviera
cada venta por separado — el mismo patrón que ya tiene
`consultar_gastos` para egresos, pero nunca se construyó el equivalente
para ventas.

**Decisión:** se agrega `sales.services.listar_ventas(company, period,
date_from, date_to, limit)` y el intent `consultar_detalle_ventas`:
cada fila trae id, fecha, cliente, total y el desglose de ítems
(producto, cantidad, precio unitario, subtotal) — la misma forma que ya
devuelve `crear_venta` para una venta individual (`SaleSerializer`),
así que el frontend reutiliza sus tipos existentes (`ReceiptLike`) en
vez de inventar una forma nueva: solo se agregó `isReceiptList` (un
array de `ReceiptLike`) a `resultShapes.ts`. Mismas reglas de
`period`/`date_from`/`date_to` que `consultar_gastos`/
`consultar_ventas_periodo` (ver ADR-022), para que "detállame esas
ventas de este mes" también funcione. En el `SYSTEM_PROMPT` se aclara
la frontera con `consultar_ventas_periodo`: si el usuario solo
pregunta CUÁNTO vendió, sin pedir ver cada venta, sigue siendo el
intent agregado — este nuevo intent es solo para cuando pide el
detalle explícitamente.

**Por qué reutilizar `ReceiptLike` en vez de una forma nueva:** una
venta con su desglose de ítems ya es exactamente lo que `crear_venta`
devuelve tras confirmarse; no había ninguna razón para que "la misma
venta, vista después" tuviera una forma de datos distinta a "la misma
venta, recién creada". Reutilizar evita duplicar la lógica de
render/voz de ítems (`Producto #N · cantidad × precio = subtotal`) que
ya existía y estaba probada.

**Nota sobre la ambigüedad de arrays vacíos:** `isReceiptList` se
revisa DESPUÉS de las demás formas en lista (`isProductList`,
`isLowStockList`, `isTopSellingList`, `isExpenseList`) tanto en
`ResultView` como en `describeResultForSpeech`, porque un array vacío
`[]` no trae ninguna pista de qué forma es — coincide con la
ambigüedad ya existente y documentada entre esas cuatro formas (la
primera del `if/else` gana). Se prioriza no alterar el mensaje que ya
mostraban esas formas para el caso vacío, aceptando que "sin ventas"
puede mostrar por accidente "sin productos en el catálogo" si el
array llega vacío — mismo trade-off ya tolerado por el código
existente, no uno nuevo introducido por esta ADR.

**Consecuencias:** nuevo intent de solo lectura, sin cambios de base
de datos. `listar_ventas` reutiliza `resolve_period_range` (ADR-022),
sin lógica de fechas nueva. El frontend gana `isReceiptList` y un
nuevo caso en `ResultView`/`describeResultForSpeech`; no se tocó
`ReceiptLike` ni la forma que ya usan compras/ventas individuales.
