"""Batería de seguridad consolidada (ver docs/ROADMAP.md Fase 11 y
docs/SECURITY.md): no reemplaza los tests de aislamiento por app (que ya
existen desde la Fase 2+ como gate obligatorio de cada fase), sino que
reúne en un solo lugar las verificaciones transversales que no son
naturales de ningún app en particular — acceso anónimo, empresa activa
obligatoria, rate limiting, y que el rastro de auditoría efectivamente
se escribe para cada flujo de escritura relevante.
"""

from decimal import Decimal
from unittest import mock

from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from accounts.factories import UserFactory
from assistant.llm_providers import FakeLLMProvider
from audit.models import AuditLog
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory, CompanyUserFactory
from companies.models import CompanyUser
from documents.image_test_helpers import make_test_image
from documents.models import Document
from documents.ocr_providers import FakeOCRProvider
from inventory.services import ajustar_inventario
from purchases.services import registrar_compra
from sales.services import crear_venta

from .throttling import CompanyScopedRateThrottle

COMPANY_HEADER = "HTTP_X_COMPANY_ID"

# Endpoints de negocio representativos (ver docs/SECURITY.md #3: toda
# vista de negocio requiere usuario autenticado). No es exhaustivo de
# cada endpoint de la API — cada app ya prueba los suyos — pero cubre al
# menos uno por módulo para detectar una regresión que afecte a
# `DEFAULT_PERMISSION_CLASSES` globalmente.
_BUSINESS_ENDPOINTS = [
    ("get", "company-list-create"),
    ("get", "product-list"),
    ("get", "sale-list-create"),
    ("get", "purchase-list-create"),
    ("get", "cashbox-summary"),
    ("get", "document-list-create"),
    ("get", "conversation-list-create"),
]


class AnonymousAccessTests(APITestCase):
    """Ver docs/SECURITY.md #3: sin sesión válida, todo lo anterior
    responde 401, nunca 200 ni 500."""

    def test_business_endpoints_reject_anonymous_requests(self):
        client = APIClient()
        for method, url_name in _BUSINESS_ENDPOINTS:
            with self.subTest(url_name=url_name):
                response = getattr(client, method)(reverse(url_name))
                self.assertEqual(response.status_code, 401)


class MissingCompanyHeaderTests(APITestCase):
    """Ver docs/SECURITY.md #3/#4: autenticado pero sin X-Company-Id
    activa siempre falla cerrado (400), nunca devuelve datos."""

    def setUp(self):
        self.user = UserFactory()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_business_endpoints_require_company_header(self):
        for method, url_name in _BUSINESS_ENDPOINTS:
            if url_name == "company-list-create":
                continue  # no depende de una empresa activa
            with self.subTest(url_name=url_name):
                response = getattr(self.client, method)(reverse(url_name))
                self.assertEqual(response.status_code, 400)


class CompanyScopedRateThrottleTests(TestCase):
    """Unit test de la pieza nueva (core/throttling.py): el cupo debe
    separarse por empresa activa, no solo por usuario/IP."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()

    def _request(self, company_id):
        request = self.factory.get("/", HTTP_X_COMPANY_ID=str(company_id))
        request.user = self.user
        return request

    def test_cache_key_differs_by_company(self):
        throttle = CompanyScopedRateThrottle()
        throttle.scope = "assistant"
        throttle.rate = "30/min"
        throttle.num_requests, throttle.duration = 30, 60

        class DummyView:
            throttle_scope = "assistant"

        key_company_1 = throttle.get_cache_key(self._request(1), DummyView())
        key_company_2 = throttle.get_cache_key(self._request(2), DummyView())

        self.assertIsNotNone(key_company_1)
        self.assertNotEqual(key_company_1, key_company_2)


class AuthThrottlingTests(APITestCase):
    """Verificación end-to-end (ver docs/SECURITY.md #2 y #9): el scope
    "auth" (login/registro/refresh) tiene un límite real de 10/min."""

    def test_repeated_bad_logins_eventually_get_throttled(self):
        client = APIClient()
        responses = [
            client.post(
                reverse("auth-login"),
                {"email": "nadie@example.cl", "password": "incorrecta"},
                format="json",
            )
            for _ in range(11)
        ]

        statuses = [r.status_code for r in responses]
        self.assertIn(429, statuses)
        # Las primeras 10 deben fallar por credenciales, no por throttle.
        self.assertTrue(all(code == 401 for code in statuses[:10]))


class AuditTrailTests(APITestCase):
    """Ver docs/SECURITY.md #10 y el criterio de aceptación de la Fase
    11: cada flujo de escritura relevante deja un AuditLog reconstruible
    (quién, qué, en qué empresa, cuándo, desde dónde)."""

    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.product = ProductFactory(company=self.company, current_stock=Decimal("100"))

    def _last_log(self, action):
        return AuditLog.objects.filter(company=self.company, action=action).latest("created_at")

    def test_crear_venta_audita_con_source_ui_por_defecto(self):
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("2")}],
        )
        log = self._last_log("sale.create")
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.source, AuditLog.Source.UI)

    def test_crear_venta_desde_el_asistente_audita_con_source_assistant(self):
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("1")}],
            origen="assistant",
        )
        log = self._last_log("sale.create")
        self.assertEqual(log.source, AuditLog.Source.ASSISTANT)

    def test_registrar_compra_audita(self):
        registrar_compra(
            company=self.company,
            user=self.user,
            items=[{"product": self.product, "quantity": Decimal("5")}],
        )
        log = self._last_log("purchase.create")
        self.assertEqual(log.source, AuditLog.Source.UI)

    def test_ajuste_manual_de_inventario_audita(self):
        ajustar_inventario(
            company=self.company,
            user=self.user,
            product=self.product,
            cantidad=Decimal("-3"),
            motivo="Merma",
        )
        log = self._last_log("inventory.adjust")
        self.assertEqual(log.after["motivo"], "Merma")
        self.assertEqual(log.source, AuditLog.Source.UI)

    def test_confirmar_documento_audita_con_source_document(self):
        client = APIClient()
        client.force_authenticate(self.user)
        headers = {COMPANY_HEADER: str(self.company.id)}

        with (
            mock.patch(
                "documents.tasks.get_ocr_provider", return_value=FakeOCRProvider("FACTURA")
            ),
            mock.patch(
                "documents.structuring.get_llm_provider",
                return_value=FakeLLMProvider(["{}"]),
            ),
        ):
            upload = client.post(
                reverse("document-list-create"),
                {"image": make_test_image()},
                format="multipart",
                **headers,
            )

        document_id = upload.data["id"]
        response = client.post(
            reverse("document-confirm", kwargs={"document_id": document_id}),
            {
                "document_type": "purchase",
                "items": [{"product_id": self.product.id, "quantity": "1", "unit_amount": "10"}],
            },
            format="json",
            **headers,
        )
        self.assertEqual(response.status_code, 200)

        log = self._last_log("document.confirm")
        self.assertEqual(log.source, AuditLog.Source.DOCUMENT)
        self.assertEqual(log.entity_id, str(document_id))

    def test_rechazar_documento_audita(self):
        document = Document.objects.create(
            company=self.company, uploaded_by=self.user, image=make_test_image()
        )
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.post(
            reverse("document-reject", kwargs={"document_id": document.id}),
            **{COMPANY_HEADER: str(self.company.id)},
        )

        self.assertEqual(response.status_code, 200)
        log = self._last_log("document.reject")
        self.assertEqual(log.source, AuditLog.Source.DOCUMENT)

    def test_login_audita(self):
        client = APIClient()
        response = client.post(
            reverse("auth-login"),
            {"email": self.user.email, "password": "TestPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        log = AuditLog.objects.filter(action="auth.login", user=self.user).latest("created_at")
        self.assertEqual(log.source, AuditLog.Source.API)

    def test_registro_audita(self):
        client = APIClient()
        response = client.post(
            reverse("auth-register"),
            {"email": "nueva@almacen.cl", "password": "OtraClave123!", "first_name": "Nueva"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        self.assertTrue(AuditLog.objects.filter(action="auth.register").exists())

    def test_crear_empresa_audita(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(
            reverse("company-list-create"), {"name": "Nueva Empresa", "rut": "11111111-1"}
        )
        self.assertEqual(response.status_code, 201)

        self.assertTrue(AuditLog.objects.filter(action="company.create").exists())
