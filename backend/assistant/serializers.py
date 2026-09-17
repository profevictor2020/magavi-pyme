from decimal import Decimal

from rest_framework import serializers

from cashbox.models import CashMovement
from catalog.models import Product
from catalog.serializers import AdjustStockSerializer

from .models import Conversation, Message


class EmptyParamsSerializer(serializers.Serializer):
    """Para intents de solo lectura que no reciben parámetros
    (consultar_ventas, consultar_stock_bajo)."""


class AjustarInventarioIntentSerializer(AdjustStockSerializer):
    product_id = serializers.IntegerField()


class ConsultarProductoIntentSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()


class ConsultarVentasProductoIntentSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()


class CrearProductoIntentSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    unit = serializers.ChoiceField(
        choices=Product.Unit.choices, required=False, default=Product.Unit.UNIDAD
    )
    default_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0")
    )
    default_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0")
    )
    initial_stock = serializers.DecimalField(
        max_digits=12, decimal_places=3, required=False, default=Decimal("0")
    )


class ActualizarProductoIntentSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField(max_length=255, required=False)
    default_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    default_cost = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    low_stock_threshold = serializers.DecimalField(
        max_digits=12, decimal_places=3, required=False
    )

    def validate(self, attrs):
        campos_editables = ("name", "default_price", "default_cost", "low_stock_threshold")
        if not any(field in attrs for field in campos_editables):
            raise serializers.ValidationError("Debes indicar al menos un campo para actualizar.")
        return attrs


class RegistrarGastoIntentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    category = serializers.ChoiceField(choices=CashMovement.Category.choices)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["category"] == CashMovement.Category.OTRO and not attrs.get("description"):
            raise serializers.ValidationError(
                {"description": 'Los gastos de categoría "otro" necesitan una descripción.'}
            )
        return attrs


class IntentEnvelopeSerializer(serializers.Serializer):
    """Forma del cuerpo de POST /api/assistant/intents/. `intent` no se
    restringe aquí a una lista cerrada de choices para evitar un import
    circular con el registro de intents (ver assistant/intents.py); la
    validación de que el nombre exista la hace
    assistant/services.py::proponer_intent, con un error igual de claro.
    """

    intent = serializers.CharField(max_length=50)
    parameters = serializers.DictField(required=False, default=dict)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "started_at", "last_message_at"]
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "structured_intent", "created_at"]
        read_only_fields = ["id", "created_at"]


class ChatMessageSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
