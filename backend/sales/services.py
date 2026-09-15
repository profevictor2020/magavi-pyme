from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum

from audit.services import registrar_auditoria
from cashbox.models import CashMovement
from core.dates import today_and_week_start
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
