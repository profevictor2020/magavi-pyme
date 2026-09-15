# MAGAVI — Backend

Django + Django REST Framework. Ver documentación del proyecto en
`../docs/` y el estado general en `../README.md`.

## Desarrollo local (sin Docker)

Requiere una instancia de PostgreSQL accesible.

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env  # y ajustar valores
python manage.py migrate
python manage.py runserver
```

## Tests y lint

```
ruff check .
pytest
```

## Apps

`core` (utilidades transversales, health check), `accounts`, `companies`,
`catalog`, `sales`, `purchases`, `inventory`, `cashbox`, `documents`,
`assistant`, `audit`. Ver `docs/ARCHITECTURE.md` para el propósito de cada
una. En esta fase están vacías (sin modelos ni endpoints de negocio).

## Endpoints

- `GET /api/health/` — healthcheck público, sin autenticación.
