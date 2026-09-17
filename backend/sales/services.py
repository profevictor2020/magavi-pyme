from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum

from audit.services import audit_source_for_origen, registrar_auditoria
from cashbox.models import CashMovement
from core.dates import resolve_period_range, today_and_week_start
from inventory.services import ajustar_inventario

from .models import Sale, SaleItem


def crear_venta(*, company, user, items, origen="manual", customer_name=""):
    """Tool Layer: único punto de escritura de ventas (ver
    docs/ARCHITECTURE.md #3.3). Usado por la API (Fase 4) y, en fases
    posteriores, por el asistente conversacional y la captura de
    documentos — sin cambios en esta función, solo en quién la llama.

    `items` es una lista de dicts {"product": Product, "quantity": Decimal,
    "unit_price": Decimal opcional (default: product.default_price)}.

    Todo ocurre en una sola transacción: si un item no tiene stock
    suficiente (ver docs/DECISIONS.md ADR-009) o el producto no pertenece
    a la empresa, no queda ninguna venta, movimiento de inventario ni de
    caja huérfanos.
    """
    if not items:
        raise ValidationError("La venta debe tener al menos un ítem.")

    with transaction.atomic():
        sale = Sale.objects.create(
            company=company,
            created_by=user,
            customer_name=customer_name,
            source=origen,
        )

        total = Decimal("0")
        sale_items = []
        for raw_item in items:
            product = raw_item["product"]
            quantity = Decimal(raw_item["quantity"])
            if quantity <= 0:
                raise ValidationError("La cantidad de cada ítem debe ser mayor a cero.")
            unit_price = Decimal(raw_item.get("unit_price") or product.default_price)
            subtotal = (quantity * unit_price).quantize(Decimal("0.01"))

            # ajustar_inventario ya valida que el producto pertenezca a la
            # empresa y rechaza dejar el stock en negativo.
            ajustar_inventario(
                company=company,
                user=user,
                product=product,
                cantidad=-quantity,
                motivo=f"Venta #{sale.id}",
                origen="sale",
                reference_id=sale.id,
            )

            sale_items.append(
                SaleItem(
                    sale=sale,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=subtotal,
                )
            )
            total += subtotal

        SaleItem.objects.bulk_create(sale_items)

        sale.total = total
        sale.save(update_fields=["total"])

        CashMovement.objects.create(
            company=company,
            type=CashMovement.MovementType.INCOME,
            amount=total,
            reference_type=CashMovement.ReferenceType.SALE,
            reference_id=sale.id,
            description=f"Venta #{sale.id}",
            created_by=user,
        )

        registrar_auditoria(
            company=company,
            user=user,
            action="sale.create",
            entity_type="Sale",
            entity_id=sale.id,
            after={"total": str(total), "items": len(sale_items)},
            source=audit_source_for_origen(origen),
        )

    return sale


def consultar_ventas(*, company):
    """Tool Layer de solo lectura: ventas de hoy y de la semana (ver
    docs/ROADMAP.md Fase 4/6/7). Usado por `GET /api/sales/summary/`,
    por `cashbox.obtener_resumen` y por el asistente conversacional.
    """
    today_start, week_start = today_and_week_start()
    base = Sale.objects.for_company(company).filter(status=Sale.Status.CONFIRMED)

    def summarize(since):
        aggregate = base.filter(sold_at__gte=since).aggregate(total=Sum("total"), count=Count("id"))
        return {
            "total": str(aggregate["total"] or Decimal("0.00")),
            "count": aggregate["count"] or 0,
        }

    return {"today": summarize(today_start), "week": summarize(week_start)}


def consultar_ventas_periodo(*, company, period=None, date_from=None, date_to=None):
    """Tool Layer de solo lectura: total vendido en un período histórico
    arbitrario — mes, año, TODO el histórico, o un rango de fechas
    explícito (ver docs/DECISIONS.md ADR-022). A diferencia de
    consultar_ventas (siempre hoy/esta semana, para "¿cómo va el
    negocio?"), esta cubre preguntas históricas: "¿cuánto llevo vendido
    en total?", "¿cuánto vendí este año?", "ventas de agosto".

    Sin period ni date_from/date_to, equivale a period="total": todo el
    histórico de ventas confirmadas, sin filtrar por fecha.
    """
    inicio, fin = resolve_period_range(period, date_from, date_to)
    base = Sale.objects.for_company(company).filter(status=Sale.Status.CONFIRMED)
    if inicio is not None:
        base = base.filter(sold_at__gte=inicio)
    if fin is not None:
        base = base.filter(sold_at__lt=fin)
    aggregate = base.aggregate(total=Sum("total"), count=Count("id"))
    return {
        "period": period or "total",
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "total": str(aggregate["total"] or Decimal("0.00")),
        "count": aggregate["count"] or 0,
    }


def consultar_ventas_producto(*, company, product):
    """Tool Layer de solo lectura: cuánto se vendió de UN producto
    puntual, hoy y en la semana (misma estructura que consultar_ventas,
    pero por cantidad de unidades en vez de solo el total en dinero).
    Para "¿cuántas gomas hemos vendido?" — consultar_ventas no sirve
    porque agrega TODAS las ventas, no filtra por producto.
    """
    today_start, week_start = today_and_week_start()
    base = SaleItem.objects.filter(
        product=product, sale__company=company, sale__status=Sale.Status.CONFIRMED
    )

    def summarize(since):
        aggregate = base.filter(sale__sold_at__gte=since).aggregate(
            quantity=Sum("quantity"), total=Sum("subtotal")
        )
        return {
            "quantity": str(aggregate["quantity"] or Decimal("0.000")),
            "total": str(aggregate["total"] or Decimal("0.00")),
        }

    return {
        "product_id": product.id,
        "product_name": product.name,
        "today": summarize(today_start),
        "week": summarize(week_start),
    }


def productos_mas_vendidos(*, company, limit=5):
    """Tool Layer de solo lectura: ranking de productos por unidades
    vendidas, contando TODAS las ventas confirmadas (sin acotar a hoy/
    semana — "¿cuál es el producto que más se ha vendido?" es una
    pregunta de siempre, no de un período puntual como consultar_ventas).
    """
    aggregates = (
        SaleItem.objects.filter(sale__company=company, sale__status=Sale.Status.CONFIRMED)
        .values("product_id", "product__name")
        .annotate(quantity=Sum("quantity"), total=Sum("subtotal"))
        .order_by("-quantity")[:limit]
    )
    return [
        {
            "product_id": row["product_id"],
            "product_name": row["product__name"],
            "quantity": str(row["quantity"]),
            "total": str(row["total"]),
        }
        for row in aggregates
    ]
