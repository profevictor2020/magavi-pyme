from django.core.exceptions import ValidationError
from django.db.models import F

from .models import Product


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
