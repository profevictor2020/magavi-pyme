# MAGAVI — Seguridad

## 1. Modelo de amenazas (principal, para un MVP con IA y multiempresa)

| # | Amenaza | Impacto | Mitigación principal |
|---|---|---|---|
| 1 | Fuga de datos entre empresas (bug de query sin filtro) | Alto — viola la promesa central del producto | Aislamiento en capas (§4), tests de aislamiento obligatorios |
| 2 | Prompt injection vía mensaje del usuario o texto OCR, intentando saltarse confirmación o leer datos de otra empresa | Alto | Contrato de intención estricto + backend nunca confía en el LLM (§5) |
| 3 | Autenticación/autorización rota (acceso sin sesión válida, escalada de rol) | Alto | JWT + permisos por vista + tests de autorización |
| 4 | Subida de archivo maliciosa (imagen de documento) | Medio | Validación de tipo/tamaño, sin ejecución, nombres aleatorios (§6) |
| 5 | Fuga de secretos (claves de firma JWT, credenciales BD) | Alto | `.env` fuera de git, gestión de secretos en despliegue (§7) |
| 6 | Registro automático de datos financieros incorrectos (por IA o por OCR) | Alto (confianza del usuario) | Confirmación humana obligatoria, nunca autoregistro (§8) |
| 7 | Abuso de recursos (spam al asistente, costo de inferencia) | Medio | Rate limiting por usuario/empresa (§9) |
| 8 | Alteración o borrado de auditoría | Alto (pierde trazabilidad) | AuditLog append-only (§10) |

## 2. Autenticación

- JWT (access token de vida corta ~15 min + refresh token) vía
  `djangorestframework-simplejwt`.
- Hash de contraseña con Argon2 (`django[argon2]`), no el PBKDF2 por
  defecto.
- Endpoints de auth con rate limiting agresivo (fuerza bruta).
- Sin "recordar sesión" indefinido: refresh token también expira y es
  revocable (blacklist) en logout.

## 3. Autorización

- Toda vista de negocio requiere: usuario autenticado **y** membresía
  activa (`CompanyUser.is_active=True`) en la empresa objetivo.
- Función central `get_current_company(request)` — único punto que
  resuelve la empresa activa; prohibido leer `company_id` directamente
  desde el body/query sin pasar por esa función y su chequeo de membresía.
- Roles MVP: `owner`, `admin`, `staff`. Operaciones de configuración de
  empresa (invitar usuarios, deshabilitar módulos) requieren `owner`/`admin`.
  Registrar ventas/compras/consultas está disponible para todos los roles.
- Deny-by-default: cualquier vista nueva sin permiso explícito debe fallar
  cerrada (403), no abierta.

## 4. Aislamiento multiempresa (defensa en profundidad)

1. Middleware resuelve `request.company` validando membresía.
2. `CompanyScopedManager`/QuerySet base que exige filtro por empresa; un
   query sin ese filtro debe lanzar error en vez de devolver todo el
   dataset (fail-closed, no fail-open).
3. El Tool Layer recibe `company` explícito en cada función — el
   aislamiento es visible en la firma del código y testeable sin HTTP.
4. Suite de tests de aislamiento (Fase 2+, gate obligatorio en cada fase
   que agregue un modelo/endpoint nuevo): crear 2 empresas con datos
   similares y verificar que ningún endpoint de la empresa A devuelve datos
   de la empresa B, ni por listado ni por acceso directo a un `id` ajeno
   (IDOR).
5. **Hardening posterior (Fase 11, no bloqueante para MVP funcional)**:
   PostgreSQL Row Level Security como segunda barrera independiente de
   bugs de aplicación.

## 5. Protección contra prompt injection y uso indebido del asistente

- El mensaje del usuario (y el texto extraído por OCR) se trata **siempre**
  como dato, nunca se concatena en la parte de "instrucciones de sistema"
  del prompt.
- El LLM solo puede proponer un `intent` dentro de un `IntentSchema` cerrado
  y versionado (whitelist de operaciones). Cualquier salida que no valide
  contra el schema se descarta y se le pide al usuario reformular — nunca
  se ejecuta "lo más parecido".
- El backend **ignora** cualquier contenido del modelo que pretenda alterar
  permisos, roles, confirmar automáticamente, cambiar de empresa activa, o
  referirse a IDs fuera de los que el propio backend resolvió por contexto
  (p.ej. el modelo no elige `company_id`, lo pone el backend).
- Toda operación de creación/edición/borrado exige confirmación explícita
  del usuario, gestionada por estado en el backend (no en el prompt ni en
  el cliente).
- Límite de acciones mutantes por turno de conversación (1), y rate
  limiting sobre el endpoint del asistente.
- Se registra el intent crudo devuelto por el modelo (`Message.
  structured_intent`) para poder auditar/depurar intentos de abuso.

## 6. Validación de archivos (captura de documentos)

- Whitelist de tipo de contenido (`image/jpeg`, `image/png`, `image/webp`;
  evaluar PDF en fase posterior).
- Límite de tamaño (p.ej. 10 MB) y de dimensiones máximas.
- Nombre de archivo generado por el backend (no se usa el nombre original
  del cliente).
- Almacenamiento fuera del webroot servido directamente; acceso solo vía
  endpoint autenticado y con scope de empresa.
- Se descartan metadatos EXIF sensibles (geolocalización) al procesar la
  imagen.

## 7. Gestión de secretos

- `.env` para configuración local, **nunca** comiteado; `.env.example` con
  placeholders documentados.
- Claves de firma JWT, credenciales de PostgreSQL/Redis y cualquier token
  inyectados como variables de entorno en el despliegue (Docker
  secrets/entorno del orquestador), nunca hardcodeados.
- `.gitignore` cubre `.env`, credenciales, dumps de base de datos y
  archivos subidos por usuarios desde el primer commit del proyecto.

## 8. Confirmación para operaciones sensibles

- Estado explícito `pending_confirmation → confirmed | cancelled` para
  toda propuesta de escritura del asistente o de un documento capturado.
- Las propuestas pendientes expiran (p.ej. 10 minutos) para evitar
  confirmaciones "fantasma" sobre contexto desactualizado (precio de
  producto cambiado entre la propuesta y la confirmación, etc. — se
  revalida al confirmar).
- Idempotencia: un `idempotency_key` por confirmación evita doble registro
  por doble tap/reintento de red.

## 9. Límites de uso / abuso

- `DRF throttling` por usuario y por empresa en: login, refresh de token, y
  endpoint del asistente.
- Límite razonable de mensajes por minuto al asistente (protege costo de
  inferencia y evita loops de abuso).

## 10. Auditoría

- `AuditLog` es append-only a nivel de aplicación (sin endpoints de
  update/delete); se documenta como deuda de hardening restringir también
  a nivel de rol de base de datos en Fase 11.
- Se audita como mínimo: creación/edición/cancelación de Sale, Purchase,
  ajustes de inventario/caja manuales, cambios de membresía
  (`CompanyUser`), confirmación de documentos, login/logout, y cualquier
  intent del asistente que resulte en escritura.
- Cada registro responde: **quién** (user), **qué** (action, entity),
  **en qué empresa** (company), **cuándo** (created_at), **desde qué
  origen** (source: ui/assistant/document/api/system).

## 11. Transporte y cabeceras

- TLS terminado en NGINX (Let's Encrypt u otro), HSTS habilitado.
- Cookies (si se usan para refresh token) con `Secure`, `HttpOnly`,
  `SameSite=Strict`.
- CORS restringido a los orígenes del frontend conocido.

## 12. Dependencias

- Versiones fijadas (`requirements.txt`/`package-lock.json`).
- Escaneo de vulnerabilidades (`pip-audit`, `npm audit`) como parte de CI —
  se activa desde Fase 1 (estructura de proyecto) aunque el enforcement
  estricto puede endurecerse en Fase 11.

## 13. Qué se detiene y se conversa antes de implementar

Cualquier decisión de diseño que toque estos puntos requiere pausa y
validación explícita antes de codificar (regla general del proyecto):

- Cambios al esquema de aislamiento multiempresa.
- Cambios a cómo el asistente obtiene/usa credenciales o contexto de
  empresa.
- Cualquier flujo que registre datos financieros sin paso de confirmación
  humana.
