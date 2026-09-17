from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from audit.services import audit_source_for_origen, registrar_auditoria
from inventory.services import ajustar_inventario

from .models import Product


def crear_producto(
    *,
    company,
    user,
    name,
    unit=Product.Unit.UNIDAD,
    sku=None,
    default_price=Decimal("0"),
    default_cost=Decimal("0"),
    low_stock_threshold=Decimal("0"),
    initial_stock=Decimal("0"),
    is_active=True,
    origen="manual",
):
    """Tool Layer: único punto de escritura de productos (mismo patrón que
    crear_venta/registrar_compra/ajustar_inventario). Usado por
    `ProductViewSet.perform_create` y por el asistente conversacional.

    El stock inicial nunca se escribe directo en `current_stock` (columna
    cacheada, ver catalog/models.py): se siembra vía `ajustar_inventario`,
    igual que cualquier otro movimiento de inventario, para que quede su
    propio registro en InventoryMovement.
    """
    if sku and Product.objects.for_company(company).filter(sku=sku).exists():
        raise ValidationError(f"Ya existe un producto con el SKU {sku} en esta empresa.")

    with transaction.atomic():
        product = Product.objects.create(
            company=company,
            name=name,
            unit=unit,
            sku=sku,
            default_price=default_price,
            default_cost=default_cost,
            low_stock_threshold=low_stock_threshold,
            is_active=is_active,
        )

        if initial_stock:
            ajustar_inventario(
                company=company,
                user=user,
                product=product,
                cantidad=initial_stock,
                motivo="Stock inicial",
                origen=origen,
            )
            product.refresh_from_db(fields=["current_stock"])

        registrar_auditoria(
            company=company,
            user=user,
            action="product.create",
            entity_type="Product",
            entity_id=product.id,
            after={"name": product.name, "default_price": str(product.default_price)},
            source=audit_source_for_origen(origen),
        )

    return product


def actualizar_producto(
    *,
    company,
    user,
    product,
    name=None,
    default_price=None,
    default_cost=None,
    low_stock_threshold=None,
    origen="manual",
):
    """Tool Layer: modifica campos de un producto ya existente (precio,
    costo, nombre, mínimo de stock bajo). Nunca toca `current_stock`
    (columna cacheada exclusiva de ajustar_inventario, ver arriba) — para
    cambiar cantidad de stock se usa ese otro flujo, no este.

    Solo se actualizan los campos recibidos con un valor: permite "el
    valor de la goma es 890" sin tener que repetir todos los demás datos
    del producto (mismo espíritu flexible de crear_producto/
    ajustar_inventario, ver docs/DECISIONS.md).
    """
    changes = {
        "name": name,
        "default_price": default_price,
        "default_cost": default_cost,
        "low_stock_threshold": low_stock_threshold,
    }
    changes = {field: value for field, value in changes.items() if value is not None}
    if not changes:
        raise ValidationError("No se indicó ningún campo para actualizar.")

    before = {field: str(getattr(product, field)) for field in changes}

    with transaction.atomic():
        for field, value in changes.items():
            setattr(product, field, value)
        product.save(update_fields=list(changes))

        registrar_auditoria(
            company=company,
            user=user,
            action="product.update",
            entity_type="Product",
            entity_id=product.id,
            before=before,
            after={field: str(value) for field, value in changes.items()},
            source=audit_source_for_origen(origen),
        )

    return product


def consultar_stock_bajo(*, company):
    """Tool Layer de solo lectura: productos con stock bajo (ver
    docs/ROADMAP.md Fase 3/6/7). Usado por `GET /api/products/?low_stock=true`
    (vía queryset directo), `cashbox.obtener_resumen` y el asistente
    conversacional — todos con el mismo criterio y el mismo formato.
    """
    products = (
        Product.objects.for_company(company)
        .filter(is_active=True, current_stock__lte=F("low_stock_threshold"))
        .order_by("name")
    )
    return [
        {
            "id": product.id,
            "name": product.name,
            "current_stock": str(product.current_stock),
            "low_stock_threshold": str(product.low_stock_threshold),
        }
        for product in products
    ]


def listar_productos(*, company):
    """Tool Layer de solo lectura: catálogo completo (productos activos),
    para "¿qué productos tenemos?"/"lista el catálogo". Usado por el
    asistente conversacional — la pantalla de Productos tiene su propio
    endpoint HTTP paginado, este es solo para la respuesta de chat.
    """
    products = Product.objects.for_company(company).filter(is_active=True).order_by("name")
    return [
        {
            "id": product.id,
            "name": product.name,
            "unit": product.unit,
            "current_stock": str(product.current_stock),
            "default_price": str(product.default_price),
        }
        for product in products
    ]


def get_product_or_raise(*, company, product_id):
    """Resuelve un product_id a una instancia Product con scope de
    empresa, para consumidores no-HTTP (el Tool Layer del asistente).
    Lanza ValidationError si no pertenece a la empresa.

    Los endpoints HTTP (catalog, sales, purchases) siguen usando
    get_object_or_404 (404, no error de validación) para no confirmar la
    existencia de recursos ajenos — ver docs/SECURITY.md #4. Esta función
    es para el contexto del asistente, donde ese matiz de IDOR por HTTP
    no aplica de la misma forma.
    """
    product = Product.objects.for_company(company).filter(pk=product_id).first()
    if product is None:
        raise ValidationError(f"El producto {product_id} no existe en esta empresa.")
    return product
