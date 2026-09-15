from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from audit.services import registrar_auditoria
from cashbox.models import CashMovement
from inventory.services import ajustar_inventario

from .models import Purchase, PurchaseItem


def registrar_compra(*, company, user, items, origen="manual", supplier_name=""):
    """Tool Layer: único punto de escritura de compras (simétrico a
    crear_venta, ver docs/ARCHITECTURE.md #3.3). Usado por la API (Fase 5)
    y, en fases posteriores, por la captura de documentos (Fase 9) y el
    asistente — sin cambios en esta función, solo en quién la llama.

    `items` es una lista de dicts {"product": Product, "quantity": Decimal,
    "unit_cost": Decimal opcional (default: product.default_cost)}.

    Todo ocurre en una sola transacción: si un ítem falla (producto de
    otra empresa, cantidad inválida), no queda ninguna compra, movimiento
    de inventario ni de caja huérfanos.
    """
    if not items:
        raise ValidationError("La compra debe tener al menos un ítem.")

    with transaction.atomic():
        purchase = Purchase.objects.create(
            company=company,
            created_by=user,
            supplier_name=supplier_name,
            source=origen,
        )

        total = Decimal("0")
        purchase_items = []
        for raw_item in items:
            product = raw_item["product"]
            quantity = Decimal(raw_item["quantity"])
            if quantity <= 0:
                raise ValidationError("La cantidad de cada ítem debe ser mayor a cero.")
            unit_cost = Decimal(raw_item.get("unit_cost") or product.default_cost)
            subtotal = (quantity * unit_cost).quantize(Decimal("0.01"))

            # ajustar_inventario ya valida que el producto pertenezca a la
            # empresa. Una compra nunca puede dejar el stock en negativo
            # (siempre suma), así que esa validación no aplica aquí.
            ajustar_inventario(
                company=company,
                user=user,
                product=product,
                cantidad=quantity,
                motivo=f"Compra #{purchase.id}",
                origen="purchase",
                reference_id=purchase.id,
            )

            purchase_items.append(
                PurchaseItem(
                    purchase=purchase,
                    product=product,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    subtotal=subtotal,
                )
            )
            total += subtotal

        PurchaseItem.objects.bulk_create(purchase_items)

        purchase.total = total
        purchase.save(update_fields=["total"])

        CashMovement.objects.create(
            company=company,
            type=CashMovement.MovementType.EXPENSE,
            amount=total,
            reference_type=CashMovement.ReferenceType.PURCHASE,
            reference_id=purchase.id,
            description=f"Compra #{purchase.id}",
            created_by=user,
        )

        registrar_auditoria(
            company=company,
            user=user,
            action="purchase.create",
            entity_type="Purchase",
            entity_id=purchase.id,
            after={"total": str(total), "items": len(purchase_items)},
        )

    return purchase
