from rest_framework import serializers

from .models import CashMovement


class CashMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashMovement
        fields = [
            "id",
            "type",
            "amount",
            "reference_type",
            "category",
            "description",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields
