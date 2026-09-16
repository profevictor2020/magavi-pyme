# Despliegue de demo en Render + Neon + DeepSeek

Ver `docs/DECISIONS.md` ADR-015 para el porqué de este camino alternativo
a `docs/DEPLOY.md` (Oracle Cloud): es un despliegue de **demo, sin datos
reales de pymes** — usa una API de LLM externa (DeepSeek) en vez de un
modelo self-hosted, algo que el proyecto normalmente no permite en
producción (ver ADR-004/ADR-010). **No cargar información real de
ningún negocio en este entorno.**

## 0. Qué se necesita antes de empezar

- Una cuenta en https://render.com (tiene tier gratuito, no pide tarjeta
  para el free tier de web services).
- Una cuenta en https://neon.tech (Postgres gratis, sin fecha de
  vencimiento — a diferencia del Postgres propio de Render, que expira a
  los 30 días).
- Una cuenta en https://platform.deepseek.com con una API key generada
  (tiene créditos gratuitos iniciales al registrarse; revisar precios
  antes de un uso intensivo).

## 1. Crear la base de datos en Neon

1. En el dashboard de Neon, **Create a project**. Cualquier región
   sirve (elige la más cercana a "Oregon" en EE.UU., donde queda el
   backend en Render, para menos latencia).
2. Neon muestra una **cadena de conexión** tipo:
   `postgresql://usuario:password@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require`
3. De ahí sacamos los valores que se van a pedir en el paso 3:
   - `POSTGRES_HOST` = la parte `ep-xxxx....neon.tech`
   - `POSTGRES_USER` = `usuario`
   - `POSTGRES_PASSWORD` = `password`
   - `POSTGRES_DB` = `neondb` (o el nombre que Neon haya asignado)
   - (El puerto y `sslmode=require` ya están fijos en `render.yaml`, no
     hace falta copiarlos.)

## 2. Conseguir la API key de DeepSeek

1. En https://platform.deepseek.com, entra a la sección de API keys y
   crea una nueva.
2. Guárdala — es el valor para `DEEPSEEK_API_KEY` en el paso 3.

## 3. Desplegar el Blueprint en Render

1. En el dashboard de Render: **New → Blueprint**.
2. Conecta tu cuenta de GitHub (si no lo has hecho) y selecciona este
   repositorio. Render detecta `render.yaml` en la raíz automáticamente.
3. Render arma un plan con dos servicios (`magavi-backend`,
   `magavi-frontend`) y pide los valores marcados `sync: false` en
   `render.yaml`:
   - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`
     → los de Neon (paso 1).
   - `DEEPSEEK_API_KEY` → la del paso 2.
4. Confirmar y crear. Render construye y despliega ambos servicios (el
   backend, al ser una imagen Docker con Tesseract, puede tardar varios
   minutos la primera vez).

## 4. Verificar

- Backend: `https://magavi-backend.onrender.com/api/health/` debería
  responder 200.
- Frontend: abrir `https://magavi-frontend.onrender.com/` — debería
  verse la pantalla de login de MAGAVI.

Si Render le agregó un sufijo a algún nombre de servicio (pasa si
"magavi-backend"/"magavi-frontend" ya estaban tomados por otra cuenta),
hay que actualizar a mano, en el dashboard de cada servicio →
Environment, las variables que asumen esas URLs fijas
(`DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS` en el backend;
`VITE_API_BASE_URL` en el frontend) con la URL real, y volver a
desplegar.

## Limitaciones de este despliegue (léelas antes de usarlo como demo)

- **Los documentos subidos no persisten**: el filesystem del backend en
  el free tier de Render es efímero — cualquier reinicio o nuevo
  despliegue borra las imágenes de boletas/facturas subidas (la fila en
  la base de datos queda, pero sin el archivo). Aceptable para probar el
  flujo, no para guardar nada real.
- **El backend "duerme"**: sin tráfico por ~15 minutos, el servicio se
  apaga y la primera request después tarda 30-50 segundos en responder
  mientras arranca de nuevo (`cold start`). Es normal, no es que esté
  caído.
- **El asistente usa DeepSeek (API externa)**: por diseño, para esto
  existe la excepción documentada en ADR-015 — nunca cargar datos reales
  de un negocio en este entorno.
- **No hay worker de Celery separado**: el procesamiento de documentos
  (OCR) corre síncrono dentro de la misma request de subida
  (`CELERY_TASK_ALWAYS_EAGER=true`, ver `render.yaml`) — la respuesta al
  subir un documento tarda unos segundos más de lo que tardaría con un
  worker aparte, pero funciona igual de bien funcionalmente.

## Actualizar el despliegue

Con `autoDeploy` en su valor por defecto, Render vuelve a desplegar
automáticamente cada vez que se hace push a la rama por defecto del
repo — no hace falta ningún paso manual.
