from rest_framework import serializers

from catalog.serializers import AdjustStockSerializer

from .models import Conversation, Message


class EmptyParamsSerializer(serializers.Serializer):
    """Para intents de solo lectura que no reciben parámetros
    (consultar_ventas, consultar_stock_bajo)."""


class AjustarInventarioIntentSerializer(AdjustStockSerializer):
    product_id = serializers.IntegerField()


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
