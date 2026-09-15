from decimal import Decimal

from rest_framework import serializers

from .models import Purchase, PurchaseItem


class PurchaseItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    unit_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal("0")
    )


class PurchaseCreateSerializer(serializers.Serializer):
    supplier_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    items = PurchaseItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("La compra debe tener al menos un ítem.")
        return value


class PurchaseItemOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseItem
        fields = ["id", "product", "quantity", "unit_cost", "subtotal"]


class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemOutputSerializer(many=True, read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id",
            "purchased_at",
            "supplier_name",
            "total",
            "status",
            "source",
            "created_at",
            "items",
        ]
        read_only_fields = fields
