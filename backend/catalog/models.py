from django.db import models

from companies.models import Company
from core.managers import CompanyScopedManager


class Product(models.Model):
    class Unit(models.TextChoices):
        UNIDAD = "unidad", "Unidad"
        KG = "kg", "Kilogramo"
        LT = "lt", "Litro"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=50, null=True, blank=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.UNIDAD)
    default_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    default_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Umbral bajo el cual el producto se considera "stock bajo". 0 (default)
    # significa que solo se marca cuando el stock llega a cero.
    low_stock_threshold = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    # Columna cacheada: se recalcula transaccionalmente en cada
    # InventoryMovement (ver inventory/services.py). Nunca se edita a mano.
    current_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CompanyScopedManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "sku"], name="unique_company_sku"),
        ]
        indexes = [
            models.Index(fields=["company", "is_active"]),
        ]

    def __str__(self):
        return self.name
