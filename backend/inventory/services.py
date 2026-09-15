from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import Product

from .models import InventoryMovement


def ajustar_inventario(
    *, company, user, product: Product, cantidad, motivo: str, origen="manual", reference_id=None
):
    """Tool Layer: único punto de escritura de movimientos de inventario.

    Usado tanto por el endpoint de ajuste manual (Fase 3) como, en fases
    posteriores, por crear_venta/registrar_compra y por el asistente
    conversacional (ver docs/ARCHITECTURE.md #3.3). `cantidad` es el delta
    con signo: positivo suma stock, negativo resta.

    No se permite que un ajuste deje el stock en negativo (ver
    docs/DECISIONS.md ADR-009): se rechaza explícitamente en vez de
    permitir stock negativo silenciosamente.
    """
    cantidad = Decimal(cantidad)
    if cantidad == 0:
        raise ValidationError("La cantidad del ajuste no puede ser cero.")

    with transaction.atomic():
        try:
            locked_product = (
                Product.objects.for_company(company).select_for_update().get(pk=product.pk)
            )
        except Product.DoesNotExist as exc:
            raise ValidationError("El producto no pertenece a la empresa indicada.") from exc

        nuevo_stock = locked_product.current_stock + cantidad
        if nuevo_stock < 0:
            raise ValidationError("El ajuste dejaría el stock en negativo.")

        movement_type = (
            InventoryMovement.MovementType.ADJUSTMENT
            if origen == "manual"
            else (
                InventoryMovement.MovementType.IN
                if cantidad > 0
                else InventoryMovement.MovementType.OUT
            )
        )

        movement = InventoryMovement.objects.create(
            company=company,
            product=locked_product,
            type=movement_type,
            quantity=cantidad,
            reference_type=origen,
            reference_id=reference_id,
            reason=motivo,
            balance_after=nuevo_stock,
            created_by=user,
        )

        locked_product.current_stock = nuevo_stock
        locked_product.save(update_fields=["current_stock", "updated_at"])

    return movement
