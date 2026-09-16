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
