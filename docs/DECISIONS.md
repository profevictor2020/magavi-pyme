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
