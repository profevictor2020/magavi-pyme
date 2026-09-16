# Despliegue en producción (Oracle Cloud Always Free)

Ver `docs/DECISIONS.md` ADR-014 para el porqué de esta elección
(self-hosting completo en una sola VM, sin proveedores externos de LLM,
sin costo). Esta guía asume una VM ya creada; si todavía no la tienes,
sigue primero los pasos de creación de cuenta/VM que se detallaron en la
conversación que dio origen a esta guía (o la sección 1 más abajo, que
los resume).

## 1. Cuenta y VM en Oracle Cloud (resumen)

1. Crear cuenta en https://www.oracle.com/cloud/free/ (pide tarjeta para
   verificar identidad, no cobra en el tier Always Free).
2. **Compute → Instances → Create Instance**:
   - Image: Ubuntu 22.04 o 24.04.
   - Shape: buscar (puede estar bajo un filtro de arquitectura "Arm",
     no junto a los shapes x86) `VM.Standard.A1.Flex` (Always Free) —
     4 OCPU / 24GB RAM (el máximo gratis).
   - Networking: "Create new virtual cloud network" + "Create new
     public subnet" si es la primera instancia de la cuenta (todavía no
     hay ninguna VCN creada) — Oracle configura solo el resto. Confirmar
     que la IP pública quede en automático.
   - SSH keys: "Generate a key pair for me" y **descargar la llave
     privada antes de crear la instancia** — no se puede recuperar
     después.
3. Anotar la **IP pública** de la instancia una vez que quede "Running".

**Si aparece "Out of capacity for shape VM.Standard.A1.Flex"**: es un
problema común y no indica ningún error de configuración — la forma ARM
gratuita es muy solicitada y la disponibilidad varía constantemente por
región. Opciones, de más a menos simple:

- Reducir a 2 OCPU / 12GB (editar el shape antes de reintentar) — a
  veces hay cupo para un tamaño menor aunque no para el máximo. Con
  12GB alcanza igual para todo el stack, usando `qwen2.5:3b-instruct`
  en vez de `qwen2.5:7b-instruct` (ver `.env.prod.example`).
- Reintentar más tarde — la capacidad se libera y ocupa constantemente.
- Suscribir la cuenta a otra región (**Governance & Administration →
  Region Management**) y crear la instancia ahí — solo funciona si la
  cuenta ya tiene cupo para regiones adicionales; una cuenta recién
  creada puede estar limitada a su home region hasta que Oracle termine
  de aprovisionarla del todo (usualmente unas horas a 1-2 días).

## 2. Firewall: dos capas, hay que abrir ambas

Una instancia de Oracle Cloud tiene **dos** firewalls independientes —
si solo se configura uno, el puerto sigue bloqueado:

**a) Security List de la VCN** (a nivel de red, en la consola OCI):
**Networking → Virtual Cloud Networks → tu VCN → Security Lists →
Default Security List → Add Ingress Rules**. Agregar reglas para los
puertos **80** (HTTP) y **443** (HTTPS, para cuando se agregue TLS —
ver sección 6). El puerto 22 (SSH) ya debería estar abierto por
defecto. **No** abrir 5432 (Postgres), 6379 (Redis), 8000 (backend) ni
11434 (Ollama) — no necesitan ser alcanzables desde fuera de la VM, y
`docker-compose.prod.yml` ya los deja sin publicar al host por este
motivo.

**b) iptables dentro de la VM**: las imágenes Ubuntu de Oracle Cloud
traen reglas de iptables propias que **bloquean todo el tráfico
entrante salvo SSH por defecto**, independientemente de lo que diga la
Security List. Sin este paso, el paso (a) por sí solo no alcanza:

```bash
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 3. Instalar Docker en la VM

```bash
ssh -i tu-llave-privada.key ubuntu@<IP_PUBLICA>

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# cerrar sesión y volver a entrar para que el grupo tome efecto
exit
ssh -i tu-llave-privada.key ubuntu@<IP_PUBLICA>
docker --version && docker compose version
```

## 4. Clonar el repo y configurar

```bash
git clone <url-del-repo> magavi-pyme
cd magavi-pyme
cp .env.prod.example .env.prod
```

Editar `.env.prod`:

- `POSTGRES_PASSWORD`: generar una contraseña real (`openssl rand -base64 24`).
- `DJANGO_SECRET_KEY`: generar una clave real (ver comentario en el
  propio archivo).
- `DJANGO_ALLOWED_HOSTS` y `DJANGO_CORS_ALLOWED_ORIGINS`: reemplazar por
  la IP pública de la VM.
- El resto de los valores por defecto (`LLM_OLLAMA_MODEL`, etc.) sirven
  tal cual para partir.

## 5. Levantar el stack

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile llm up --build -d
```

Esto construye las imágenes de backend (gunicorn) y frontend (build de
producción servido por NGINX — ver `frontend/Dockerfile.prod`), corre
migraciones y `collectstatic` automáticamente (ver
`backend/docker-entrypoint.sh`), y deja todo escuchando en el puerto 80.

Verificar que todo esté sano:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
curl http://localhost/api/health/
```

Descargar el modelo del asistente (una sola vez; son varios GB, puede
tardar varios minutos):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec llm-inference ollama pull qwen2.5:7b-instruct
```

(Usar el mismo nombre configurado en `LLM_OLLAMA_MODEL` en `.env.prod`.)

Crear un usuario para poder entrar a la app (o hacerlo desde la
pantalla de registro del frontend):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py createsuperuser
```

## 6. Verificar

Abrir `http://<IP_PUBLICA>/` desde un celular o navegador. Debería verse
la pantalla de login de MAGAVI, instalable como PWA. Repetir (a mano, o
reutilizando `frontend/e2e/demo.spec.ts` apuntando `VITE_API_BASE_URL`/
`baseURL` de Playwright a esta IP) el guion de la Fase 12 para confirmar
que el despliegue real funciona igual que en el entorno de desarrollo.

**Sin HTTPS todavía**: el tráfico entre el navegador y la VM va sin
cifrar (ver sección 6 más abajo). Aceptable para una demo/piloto
inicial, no para manejar datos sensibles de producción real de forma
indefinida.

## 7. Actualizar el despliegue (nuevos cambios)

```bash
cd magavi-pyme
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile llm up --build -d
```

Como `backend`/`worker` no usan bind mount en producción (a diferencia
de desarrollo), hace falta `--build` para que el código nuevo quede
efectivamente en la imagen.

## 8. Respaldo de la base de datos

No hay automatizado todavía (queda como mejora futura, no bloqueante
para un piloto). Respaldo manual:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec postgres \
  pg_dump -U magavi magavi > backup-$(date +%Y%m%d).sql
```

## 9. HTTPS con dominio propio (opcional, pendiente)

Sin un dominio no se puede emitir un certificado TLS válido (Let's
Encrypt no emite certificados para IPs públicas desnudas). Cuando se
tenga un dominio apuntando a la IP de la VM:

1. Agregar un contenedor Caddy o Certbot+NGINX delante del `frontend`
   actual (o reemplazar NGINX por Caddy, que gestiona el certificado
   automáticamente).
2. Poner `DJANGO_SECURE_SSL_REDIRECT=true` en `.env.prod`.
3. Abrir el puerto 443 en la Security List e iptables (sección 2).

Esto queda fuera del alcance de este despliegue inicial — ver
`docs/DECISIONS.md` ADR-014.

## Troubleshooting

- **`curl http://localhost/api/health/` no responde**: revisar
  `docker compose -f docker-compose.prod.yml --env-file .env.prod logs backend`.
  La causa más común es `DJANGO_ALLOWED_HOSTS` sin la IP correcta (Django
  responde 400 a cualquier Host no listado).
- **El asistente no responde / da error**: confirmar que el modelo ya
  se descargó (`docker compose ... exec llm-inference ollama list`) —
  el primer mensaje después de un `ollama pull` recién terminado además
  puede demorar más de lo normal mientras el modelo se carga en RAM.
- **Puerto 80 no responde desde fuera de la VM pero sí con
  `curl http://localhost/` dentro de ella**: falta abrir el puerto en la
  Security List, en iptables, o ambos (ver sección 2) — es el problema
  más común de todos.
