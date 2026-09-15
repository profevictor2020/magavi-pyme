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

`core` (utilidades transversales: health check, `tenancy.py` con
`get_current_company`, `managers.py` con `CompanyScopedManager`),
`accounts` (usuario custom + JWT), `companies` (Company, CompanyUser,
Module, CompanyModule), `catalog`, `sales`, `purchases`, `inventory`,
`cashbox`, `documents`, `assistant`, `audit`. Ver `docs/ARCHITECTURE.md`
para el propósito de cada una. Desde `catalog` en adelante siguen vacías
(sin modelos ni endpoints de negocio) hasta su fase correspondiente.

## Endpoints

- `GET /api/health/` — healthcheck público, sin autenticación.
- `POST /api/auth/register/` — registro (devuelve access + refresh).
- `POST /api/auth/login/` — login con `email`/`password` (devuelve access
  + refresh).
- `POST /api/auth/refresh/` — refresca el access token.
- `POST /api/auth/logout/` — invalida (blacklist) el refresh token.
- `GET /api/auth/me/` — usuario autenticado actual.
- `GET/POST /api/companies/` — "mis empresas" / crear empresa (el creador
  queda como `owner`).
- `GET /api/companies/<id>/` — detalle, solo si el usuario tiene
  membresía activa (404 si no, nunca 403, para no confirmar existencia).

Los endpoints de negocio (productos, ventas, etc., a partir de Fase 3)
requerirán además el header `X-Company-Id` con la empresa activa; ver
`core/tenancy.py`.
