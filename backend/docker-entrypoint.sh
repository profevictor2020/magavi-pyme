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

python manage.py migrate --noinput

exec "$@"
