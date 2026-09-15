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
Module, CompanyModule), `catalog` (Product), `inventory`
(InventoryMovement + Tool Layer `ajustar_inventario`), `sales` (Sale,
SaleItem + Tool Layer `crear_venta`), `purchases` (Purchase,
PurchaseItem + Tool Layer `registrar_compra`), `cashbox` (CashMovement,
escrito por `crear_venta`/`registrar_compra`; sin endpoints propios
todavía), `audit` (AuditLog append-only, escrito por el Tool Layer; sin
endpoints todavía), `documents`, `assistant`. Ver `docs/ARCHITECTURE.md`
para el propósito de cada una. `documents` y `assistant` siguen vacías
hasta su fase correspondiente.

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
- `GET/POST /api/products/` — listar/crear productos. `POST` acepta
  `initial_stock` opcional (siembra el stock inicial vía
  `ajustar_inventario`). `GET ?low_stock=true` filtra los productos con
  `current_stock <= low_stock_threshold`.
- `GET/PATCH/PUT /api/products/<id>/` — detalle/edición. Sin `DELETE`
  (405): no hay borrado físico, se desactiva con `is_active`.
- `POST /api/products/<id>/adjust-stock/` — ajuste manual de stock
  (`{"cantidad": "-3", "motivo": "..."}`); rechaza dejar el stock en
  negativo (ver `docs/DECISIONS.md` ADR-009).
- `GET/POST /api/sales/` — listar (con filtros opcionales `?from=` /
  `?to=`, formato `YYYY-MM-DD`) / crear una venta:
  `{"items": [{"product_id": 1, "quantity": "3", "unit_price": "2500.00"}], "customer_name": "..."}`
  (`unit_price` es opcional, por defecto `Product.default_price`).
  Actualiza stock e ingreso de caja en la misma transacción (Tool Layer
  `crear_venta`).
- `GET /api/sales/summary/` — `{"today": {"total": ..., "count": ...},
  "week": {...}}`, soporte directo a "¿cuánto vendí hoy?" del guion de
  demo.
- `GET/POST /api/purchases/` — análogo a `/api/sales/`: listar (con
  filtros `?from=`/`?to=`) / registrar una compra:
  `{"supplier_name": "...", "items": [{"product_id": 1, "quantity": "20", "unit_cost": "1500.00"}]}`
  (`unit_cost` opcional, por defecto `Product.default_cost`). Sube stock
  y registra el egreso de caja (Tool Layer `registrar_compra`).
- `GET /api/purchases/summary/` — compras/egresos de hoy y de la semana.

Todos los endpoints de negocio requieren el header `X-Company-Id` con la
empresa activa; ver `core/tenancy.py`.
