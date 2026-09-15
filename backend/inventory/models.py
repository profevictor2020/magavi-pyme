from django.conf import settings
from django.db import models

from catalog.models import Product
from companies.models import Company
from core.managers import CompanyScopedManager


class InventoryMovement(models.Model):
    class MovementType(models.TextChoices):
        IN = "in", "Entrada"
        OUT = "out", "Salida"
        ADJUSTMENT = "adjustment", "Ajuste"

    class ReferenceType(models.TextChoices):
        SALE = "sale", "Venta"
        PURCHASE = "purchase", "Compra"
        MANUAL = "manual", "Manual"

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="inventory_movements"
    )
    # PROTECT: nunca se borra físicamente un producto con historial de
    # movimientos (ver docs/DATA_MODEL.md #1, "no hay borrado físico").
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="inventory_movements"
    )
    type = models.CharField(max_length=10, choices=MovementType.choices)
    # Delta con signo: positivo suma stock, negativo resta.
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    reference_type = models.CharField(
        max_length=10, choices=ReferenceType.choices, default=ReferenceType.MANUAL
    )
    reference_id = models.PositiveBigIntegerField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    balance_after = models.DecimalField(max_digits=14, decimal_places=3)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inventory_movements"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyScopedManager()

    class Meta:
        indexes = [
            models.Index(fields=["company", "created_at"]),
        ]

    def __str__(self):
        return f"{self.type} {self.quantity} {self.product} ({self.company})"
