from django.conf import settings
from django.db import models

from companies.models import Company
from core.managers import CompanyScopedManager


class CashMovement(models.Model):
    class MovementType(models.TextChoices):
        INCOME = "income", "Ingreso"
        EXPENSE = "expense", "Egreso"

    class ReferenceType(models.TextChoices):
        SALE = "sale", "Venta"
        PURCHASE = "purchase", "Compra"
        MANUAL = "manual", "Manual"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="cash_movements")
    type = models.CharField(max_length=10, choices=MovementType.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference_type = models.CharField(
        max_length=10, choices=ReferenceType.choices, default=ReferenceType.MANUAL
    )
    reference_id = models.PositiveBigIntegerField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_movements"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyScopedManager()

    class Meta:
        indexes = [
            models.Index(fields=["company", "created_at"]),
        ]

    def __str__(self):
        return f"{self.type} {self.amount} ({self.company})"
