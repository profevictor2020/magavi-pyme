#!/bin/sh
set -e

if [ -n "$POSTGRES_HOST" ]; then
  echo "Esperando PostgreSQL en $POSTGRES_HOST:${POSTGRES_PORT:-5432}..."
  while ! python - <<'PYEOF'
import os
import socket
import sys

host = os.environ.get("POSTGRES_HOST", "localhost")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(1)
try:
    sock.connect((host, port))
except OSError:
    sys.exit(1)
else:
    sys.exit(0)
finally:
    sock.close()
PYEOF
  do
    sleep 1
  done
  echo "PostgreSQL disponible."
fi

if [ "$SKIP_MIGRATIONS" != "true" ]; then
  python manage.py migrate --noinput
  # collectstatic solo importa para el servicio que sirve HTTP (backend),
  # no para el worker de Celery — se reutiliza la misma condición porque
  # es exactamente la que ya distingue a ambos (ver docker-compose*.yml).
  python manage.py collectstatic --noinput
fi

exec "$@"
