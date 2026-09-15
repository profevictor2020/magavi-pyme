from django.conf import settings
from django.db import models

from catalog.models import Product
from companies.models import Company
from core.managers import CompanyScopedManager


class Purchase(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmada"
        CANCELLED = "cancelled", "Cancelada"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        ASSISTANT = "assistant", "Asistente"
        DOCUMENT = "document", "Documento"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="purchases")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchases"
    )
    purchased_at = models.DateTimeField(auto_now_add=True)
    # Texto libre para el MVP (ver docs/DATA_MODEL.md: no hay entidad
    # Supplier todavía).
    supplier_name = models.CharField(max_length=255, blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyScopedManager()

    class Meta:
        indexes = [
            models.Index(fields=["company", "purchased_at"]),
        ]

    def __str__(self):
        return f"Compra #{self.pk} ({self.company})"


class PurchaseItem(models.Model):
    # Sin `company` propio: siempre se accede a través de
    # `purchase.company` (igual que SaleItem).
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    # PROTECT: no se puede borrar un producto con historial de compras.
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchase_items")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product} (compra {self.purchase_id})"
