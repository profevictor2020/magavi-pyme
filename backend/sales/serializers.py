from decimal import Decimal

from rest_framework import serializers

from .models import Sale, SaleItem


class SaleItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal("0")
    )


class SaleCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    items = SaleItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("La venta debe tener al menos un ítem.")
        return value


class SaleItemOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = ["id", "product", "quantity", "unit_price", "subtotal"]


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemOutputSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "sold_at",
            "customer_name",
            "total",
            "status",
            "source",
            "created_at",
            "items",
        ]
        read_only_fields = fields
