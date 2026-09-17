from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from cashbox.models import CashMovement
from cashbox.serializers import CashMovementSerializer
from catalog.models import Product
from catalog.serializers import InventoryMovementSerializer, ProductSerializer
from core.tenancy import get_current_company
from core.throttling import CompanyScopedRateThrottle
from inventory.models import InventoryMovement
from purchases.models import Purchase
from purchases.serializers import PurchaseSerializer
from sales.models import Sale
from sales.serializers import SaleSerializer

from .models import Conversation
from .orchestrator import interpretar_y_proponer
from .serializers import (
    ChatMessageSerializer,
    ConversationSerializer,
    IntentEnvelopeSerializer,
    MessageSerializer,
)
from .services import cancelar_intent, confirmar_intent, proponer_intent

# Los intents mutantes devuelven la instancia real creada por el Tool
# Layer (ver docs/ARCHITECTURE.md #3.3); aquí se serializa igual que en
# el endpoint HTTP equivalente, para no filtrar un objeto Django crudo
# en la respuesta.
_RESULT_SERIALIZERS = {
    Sale: SaleSerializer,
    Purchase: PurchaseSerializer,
    InventoryMovement: InventoryMovementSerializer,
    Product: ProductSerializer,
    CashMovement: CashMovementSerializer,
}


def _as_drf_validation_error(exc: DjangoValidationError) -> DRFValidationError:
    return DRFValidationError(exc.messages)


def _serialize_result(resultado):
    serializer_class = _RESULT_SERIALIZERS.get(type(resultado))
    if serializer_class is None:
        # Los intents de solo lectura ya devuelven dicts planos.
        return resultado
    return serializer_class(resultado).data


class ConversationListCreateView(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer

    def get_queryset(self):
        company = get_current_company(self.request)
        return (
            Conversation.objects.for_company(company)
            .filter(user=self.request.user)
            .order_by("-last_message_at")
        )

    def perform_create(self, serializer):
        company = get_current_company(self.request)
        serializer.save(company=company, user=self.request.user)


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer

    def _get_conversation(self):
        company = get_current_company(self.request)
        conversation = (
            Conversation.objects.for_company(company)
            .filter(pk=self.kwargs["conversation_id"], user=self.request.user)
            .first()
        )
        if conversation is None:
            raise Http404
        return conversation

    def get_queryset(self):
        return self._get_conversation().messages.order_by("created_at")

    def perform_create(self, serializer):
        conversation = self._get_conversation()
        serializer.save(conversation=conversation)
        Conversation.objects.filter(pk=conversation.pk).update(last_message_at=timezone.now())


class IntentProposeView(APIView):
    """POST {"intent": "crear_venta", "parameters": {...}, "conversation_id": opcional}.

    Valida el intent y, si es mutante, crea una propuesta pendiente de
    confirmación en vez de ejecutarla (ver docs/ARCHITECTURE.md #3.4).
    """

    throttle_classes = [CompanyScopedRateThrottle]
    throttle_scope = "assistant"

    def post(self, request):
        company = get_current_company(request)
        envelope = IntentEnvelopeSerializer(data=request.data)
        envelope.is_valid(raise_exception=True)

        conversation = None
        conversation_id = envelope.validated_data.get("conversation_id")
        if conversation_id is not None:
            conversation = (
                Conversation.objects.for_company(company)
                .filter(pk=conversation_id, user=request.user)
                .first()
            )
            if conversation is None:
                return Response(
                    {"detail": "Conversación no encontrada."}, status=status.HTTP_404_NOT_FOUND
                )

        try:
            resultado = proponer_intent(
                company=company,
                user=request.user,
                intent_name=envelope.validated_data["intent"],
                raw_parameters=envelope.validated_data["parameters"],
                conversation=conversation,
            )
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc) from exc

        response_status = (
            status.HTTP_201_CREATED
            if resultado["status"] == "pending_confirmation"
            else status.HTTP_200_OK
        )
        return Response(resultado, status=response_status)


class IntentConfirmView(APIView):
    throttle_classes = [CompanyScopedRateThrottle]
    throttle_scope = "assistant"

    def post(self, request, pending_action_id):
        company = get_current_company(request)
        try:
            resultado = confirmar_intent(
                company=company, user=request.user, pending_action_id=pending_action_id
            )
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc) from exc

        return Response({"status": "confirmed", "result": _serialize_result(resultado)})


class ChatView(APIView):
    """POST {"message": "Vendí 3 cafés a 2500", "conversation_id": opcional}.

    Punto de entrada del asistente en lenguaje natural (ver
    docs/ROADMAP.md Fase 8): traduce el mensaje a un intent vía el LLM
    configurado y lo propone igual que /api/assistant/intents/ (Fase 7)
    — toda mutación sigue requiriendo confirmación explícita, el LLM
    nunca ejecuta nada directamente.
    """

    throttle_classes = [CompanyScopedRateThrottle]
    throttle_scope = "assistant"

    def post(self, request):
        company = get_current_company(request)
        serializer = ChatMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conversation_id = serializer.validated_data.get("conversation_id")
        if conversation_id is not None:
            conversation = (
                Conversation.objects.for_company(company)
                .filter(pk=conversation_id, user=request.user)
                .first()
            )
            if conversation is None:
                return Response(
                    {"detail": "Conversación no encontrada."}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            conversation = Conversation.objects.create(company=company, user=request.user)

        resultado = interpretar_y_proponer(
            company=company,
            user=request.user,
            mensaje=serializer.validated_data["message"],
            conversation=conversation,
        )

        Conversation.objects.filter(pk=conversation.pk).update(last_message_at=timezone.now())

        return Response({"conversation_id": conversation.id, **resultado})


class IntentCancelView(APIView):
    def post(self, request, pending_action_id):
        company = get_current_company(request)
        try:
            pending = cancelar_intent(
                company=company, user=request.user, pending_action_id=pending_action_id
            )
        except DjangoValidationError as exc:
            raise _as_drf_validation_error(exc) from exc

        return Response({"status": pending.status})
