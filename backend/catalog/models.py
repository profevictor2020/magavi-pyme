from decimal import ROUND_HALF_UP, Decimal

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


def formatear_cantidad(cantidad, unit: str) -> str:
    """Formatea una cantidad para texto libre (ver
    assistant/orchestrator.py, docs/DECISIONS.md ADR-024): el stock y
    las cantidades vendidas se guardan con 3 decimales para soportar
    kg/lt fraccionarios (ver Product.current_stock), pero mostrarle al
    LLM "10.000" para algo vendido por unidad — un conteo entero — se
    lee como si fuera un decimal real, y el modelo lo repite tal cual
    en una respuesta de texto libre (responder/asesoria), donde nadie
    lo recorta como sí hace el frontend (formatQuantity) para las
    formas estructuradas.

    Para unit="unidad" siempre redondea a entero: nunca tiene sentido
    vender "3.5 unidades". Para kg/lt preserva decimales reales, solo
    recorta los ceros de más ("2.500" -> "2.5", "10.000" -> "10").
    """
    numero = Decimal(str(cantidad))
    if unit == Product.Unit.UNIDAD:
        return str(int(numero.to_integral_value(rounding=ROUND_HALF_UP)))
    entero = numero.to_integral_value()
    if numero == entero:
        return str(int(numero))
    return f"{numero.normalize():f}"
