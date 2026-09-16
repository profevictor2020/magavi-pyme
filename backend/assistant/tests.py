import json
from decimal import Decimal
from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.factories import UserFactory
from audit.models import AuditLog
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory, CompanyUserFactory
from companies.models import CompanyUser
from sales.models import Sale

from .llm_providers import FakeLLMProvider
from .models import Conversation, PendingAction

COMPANY_HEADER = "HTTP_X_COMPANY_ID"


class IntentProposeConfirmFlowTests(APITestCase):
    """Integration: propuesta -> confirmación -> ejecución -> auditoría,
    vía API, sin LLM (ver docs/ROADMAP.md Fase 7)."""

    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user)
        self.headers = {COMPANY_HEADER: str(self.company.id)}
        self.product = ProductFactory(
            company=self.company, default_price=Decimal("2500.00"), current_stock=Decimal("10")
        )

    def test_full_flow_crear_venta(self):
        propose_response = self.client.post(
            reverse("intent-propose"),
            {
                "intent": "crear_venta",
                "parameters": {"items": [{"product_id": self.product.id, "quantity": "3"}]},
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(propose_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(propose_response.data["status"], "pending_confirmation")
        pending_id = propose_response.data["pending_action_id"]

        # Nada se ejecutó todavía: la propuesta no muta nada.
        self.assertEqual(Sale.objects.for_company(self.company).count(), 0)

        confirm_response = self.client.post(
            reverse("intent-confirm", kwargs={"pending_action_id": pending_id}), **self.headers
        )

        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertEqual(confirm_response.data["result"]["total"], "7500.00")
        self.assertEqual(Sale.objects.for_company(self.company).count(), 1)

        self.assertTrue(
            AuditLog.objects.filter(company=self.company, action="sale.create").exists()
        )

        pending = PendingAction.objects.for_company(self.company).get(pk=pending_id)
        self.assertEqual(pending.status, PendingAction.Status.CONFIRMED)

    def test_readonly_intent_executes_without_confirmation_step(self):
        response = self.client.post(
            reverse("intent-propose"),
            {"intent": "consultar_stock_bajo", "parameters": {}},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "executed")

    def test_cancel_flow_prevents_confirmation(self):
        propose_response = self.client.post(
            reverse("intent-propose"),
            {
                "intent": "crear_venta",
                "parameters": {"items": [{"product_id": self.product.id, "quantity": "1"}]},
            },
            format="json",
            **self.headers,
        )
        pending_id = propose_response.data["pending_action_id"]

        cancel_response = self.client.post(
            reverse("intent-cancel", kwargs={"pending_action_id": pending_id}), **self.headers
        )
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_response.data["status"], "cancelled")

        confirm_response = self.client.post(
            reverse("intent-confirm", kwargs={"pending_action_id": pending_id}), **self.headers
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Sale.objects.for_company(self.company).count(), 0)

    def test_propose_requires_company_header(self):
        response = self.client.post(
            reverse("intent-propose"),
            {"intent": "consultar_stock_bajo", "parameters": {}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_propose_with_unknown_intent_returns_400(self):
        response = self.client.post(
            reverse("intent-propose"),
            {"intent": "hacer_magia", "parameters": {}},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ConversationMessageTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user)
        self.headers = {COMPANY_HEADER: str(self.company.id)}

    def test_create_conversation_and_post_message(self):
        conv_response = self.client.post(
            reverse("conversation-list-create"), {}, format="json", **self.headers
        )
        self.assertEqual(conv_response.status_code, status.HTTP_201_CREATED)
        conversation_id = conv_response.data["id"]

        msg_response = self.client.post(
            reverse("message-list-create", kwargs={"conversation_id": conversation_id}),
            {"role": "user", "content": "Vendí 3 cafés"},
            format="json",
            **self.headers,
        )
        self.assertEqual(msg_response.status_code, status.HTTP_201_CREATED)

        list_response = self.client.get(
            reverse("message-list-create", kwargs={"conversation_id": conversation_id}),
            **self.headers,
        )
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["content"], "Vendí 3 cafés")

    def test_cannot_post_message_to_foreign_conversation(self):
        other_company = CompanyFactory()
        other_user = UserFactory()
        CompanyUserFactory(company=other_company, user=other_user, role=CompanyUser.Role.OWNER)
        other_client = APIClient()
        other_client.force_authenticate(other_user)
        conv = other_client.post(
            reverse("conversation-list-create"),
            {},
            format="json",
            **{COMPANY_HEADER: str(other_company.id)},
        )

        response = self.client.post(
            reverse("message-list-create", kwargs={"conversation_id": conv.data["id"]}),
            {"role": "user", "content": "intento cruzado"},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class IntentIsolationTests(APITestCase):
    """Gate obligatorio de aislamiento multiempresa (docs/TESTING.md #2)."""

    def setUp(self):
        self.user_a = UserFactory()
        self.company_a = CompanyFactory()
        CompanyUserFactory(company=self.company_a, user=self.user_a, role=CompanyUser.Role.OWNER)
        self.client_a = APIClient()
        self.client_a.force_authenticate(self.user_a)

        self.company_b = CompanyFactory()
        self.user_b = UserFactory()
        CompanyUserFactory(company=self.company_b, user=self.user_b, role=CompanyUser.Role.OWNER)
        self.client_b = APIClient()
        self.client_b.force_authenticate(self.user_b)
        self.product_b = ProductFactory(company=self.company_b, current_stock=Decimal("10"))

    def test_cannot_execute_intent_referencing_foreign_product(self):
        propose_response = self.client_a.post(
            reverse("intent-propose"),
            {
                "intent": "crear_venta",
                "parameters": {"items": [{"product_id": self.product_b.id, "quantity": "1"}]},
            },
            format="json",
            **{COMPANY_HEADER: str(self.company_a.id)},
        )

        # La forma es válida (product_id es un entero cualquiera); lo
        # que debe fallar es la ejecución/confirmación, que resuelve el
        # producto con scope de empresa.
        self.assertEqual(propose_response.status_code, status.HTTP_201_CREATED)
        pending_id = propose_response.data["pending_action_id"]

        confirm_response = self.client_a.post(
            reverse("intent-confirm", kwargs={"pending_action_id": pending_id}),
            **{COMPANY_HEADER: str(self.company_a.id)},
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_confirm_pending_action_belonging_to_another_company(self):
        propose_b = self.client_b.post(
            reverse("intent-propose"),
            {
                "intent": "crear_venta",
                "parameters": {"items": [{"product_id": self.product_b.id, "quantity": "1"}]},
            },
            format="json",
            **{COMPANY_HEADER: str(self.company_b.id)},
        )
        pending_id = propose_b.data["pending_action_id"]

        confirm_from_a = self.client_a.post(
            reverse("intent-confirm", kwargs={"pending_action_id": pending_id}),
            **{COMPANY_HEADER: str(self.company_a.id)},
        )
        self.assertEqual(confirm_from_a.status_code, status.HTTP_400_BAD_REQUEST)


class ChatViewTests(APITestCase):
    """Integration del endpoint de chat en lenguaje natural (Fase 8),
    con un LLMProvider falso inyectado vía mock — sin GPU ni proveedor
    externo real (ver docs/ROADMAP.md Fase 8).
    """

    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user)
        self.headers = {COMPANY_HEADER: str(self.company.id)}
        self.product = ProductFactory(
            company=self.company, default_price=Decimal("2500.00"), current_stock=Decimal("10")
        )

    def _mock_llm(self, respuestas):
        fake = FakeLLMProvider(respuestas)
        return mock.patch("assistant.orchestrator.get_llm_provider", return_value=fake), fake

    def test_chat_crea_conversacion_y_propuesta(self):
        raw = json.dumps(
            {
                "intent": "crear_venta",
                "parameters": {"items": [{"product_id": self.product.id, "quantity": "3"}]},
            }
        )
        patcher, _fake = self._mock_llm([raw])

        with patcher:
            response = self.client.post(
                reverse("assistant-chat"),
                {"message": "Vendí 3 cafés"},
                format="json",
                **self.headers,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "pending_confirmation")
        conversation_id = response.data["conversation_id"]
        self.assertTrue(Conversation.objects.for_company(self.company).filter(pk=conversation_id).exists())

        pending_id = response.data["pending_action_id"]
        confirm = self.client.post(
            reverse("intent-confirm", kwargs={"pending_action_id": pending_id}), **self.headers
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        self.assertEqual(Sale.objects.for_company(self.company).count(), 1)

    def test_chat_continua_una_conversacion_existente(self):
        conv_response = self.client.post(
            reverse("conversation-list-create"), {}, format="json", **self.headers
        )
        conversation_id = conv_response.data["id"]

        respuesta = json.dumps({"intent": "consultar_stock_bajo", "parameters": {}})
        patcher, _fake = self._mock_llm([respuesta])

        with patcher:
            response = self.client.post(
                reverse("assistant-chat"),
                {"message": "¿algo con poco stock?", "conversation_id": conversation_id},
                format="json",
                **self.headers,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["conversation_id"], conversation_id)
        conversation = Conversation.objects.for_company(self.company).get(pk=conversation_id)
        self.assertEqual(conversation.messages.count(), 2)

    def test_chat_con_conversacion_ajena_devuelve_404(self):
        other_company = CompanyFactory()
        other_user = UserFactory()
        CompanyUserFactory(company=other_company, user=other_user, role=CompanyUser.Role.OWNER)
        other_client = APIClient()
        other_client.force_authenticate(other_user)
        foreign_conv = other_client.post(
            reverse("conversation-list-create"),
            {},
            format="json",
            **{COMPANY_HEADER: str(other_company.id)},
        )

        response = self.client.post(
            reverse("assistant-chat"),
            {"message": "hola", "conversation_id": foreign_conv.data["id"]},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_chat_mensaje_ambiguo_pide_aclaracion(self):
        patcher, _fake = self._mock_llm(
            [json.dumps({"intent": "no_entendido", "parameters": {"motivo": "falta la cantidad"}})]
        )

        with patcher:
            response = self.client.post(
                reverse("assistant-chat"), {"message": "vendí cafés"}, format="json", **self.headers
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "no_entendido")
