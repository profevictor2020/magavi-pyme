from decimal import Decimal

from rest_framework import serializers

from inventory.models import InventoryMovement

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    # Solo se usa al crear: siembra el stock inicial vía el Tool Layer de
    # inventario (ajustar_inventario), nunca escribiendo current_stock
    # directo. Ver catalog/views.py.
    initial_stock = serializers.DecimalField(
        max_digits=12, decimal_places=3, write_only=True, required=False, default=Decimal("0")
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "unit",
            "default_price",
            "default_cost",
            "low_stock_threshold",
            "current_stock",
            "is_active",
            "created_at",
            "updated_at",
            "initial_stock",
        ]
        read_only_fields = ["id", "current_stock", "created_at", "updated_at"]

    def validate(self, attrs):
        sku = attrs.get("sku")
        if sku:
            company = self.context["company"]
            qs = Product.objects.for_company(company).filter(sku=sku)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"sku": "Ya existe un producto con este SKU en la empresa."}
                )
        return attrs


class AdjustStockSerializer(serializers.Serializer):
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=3)
    motivo = serializers.CharField(max_length=255)

    def validate_cantidad(self, value):
        if value == 0:
            raise serializers.ValidationError("La cantidad no puede ser cero.")
        return value


class InventoryMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryMovement
        fields = [
            "id",
            "product",
            "type",
            "quantity",
            "reference_type",
            "reason",
            "balance_after",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields
