import json
from decimal import Decimal
from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.factories import UserFactory
from assistant.llm_providers import FakeLLMProvider
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory, CompanyUserFactory
from companies.models import CompanyUser
from purchases.models import Purchase

from .image_test_helpers import make_test_image
from .models import Document
from .ocr_providers import FakeOCRProvider

COMPANY_HEADER = "HTTP_X_COMPANY_ID"


def _mock_pipeline(ocr_text="FACTURA", llm_response=None):
    llm_response = llm_response or json.dumps(
        {
            "document_type": "purchase",
            "counterparty_name": "Proveedor X",
            "items": [],
            "total": None,
        }
    )
    ocr_patch = mock.patch(
        "documents.tasks.get_ocr_provider", return_value=FakeOCRProvider(ocr_text)
    )
    llm_patch = mock.patch(
        "documents.structuring.get_llm_provider", return_value=FakeLLMProvider([llm_response])
    )
    return ocr_patch, llm_patch


class DocumentUploadTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user)
        self.headers = {COMPANY_HEADER: str(self.company.id)}

    def test_upload_creates_document_and_processes_it(self):
        ocr_patch, llm_patch = _mock_pipeline()

        with ocr_patch, llm_patch:
            response = self.client.post(
                reverse("document-list-create"),
                {"image": make_test_image()},
                format="multipart",
                **self.headers,
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = Document.objects.for_company(self.company).get(pk=response.data["id"])
        # CELERY_TASK_ALWAYS_EAGER hace que la tarea corra en el mismo
        # request (ver config/settings.py), así que ya debería estar
        # lista para revisión.
        self.assertEqual(document.status, Document.Status.NEEDS_REVIEW)

    def test_upload_requires_company_header(self):
        response = self.client.post(
            reverse("document-list-create"), {"image": make_test_image()}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_rejects_invalid_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        bad_file = SimpleUploadedFile(
            "archivo.exe", b"no soy una imagen", content_type="application/exe"
        )

        response = self.client.post(
            reverse("document-list-create"), {"image": bad_file}, format="multipart", **self.headers
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_documents(self):
        ocr_patch, llm_patch = _mock_pipeline()
        with ocr_patch, llm_patch:
            self.client.post(
                reverse("document-list-create"),
                {"image": make_test_image()},
                format="multipart",
                **self.headers,
            )

        response = self.client.get(reverse("document-list-create"), **self.headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIsNotNone(response.data[0]["extraction"])


class DocumentConfirmRejectTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user)
        self.headers = {COMPANY_HEADER: str(self.company.id)}
        self.product = ProductFactory(company=self.company, current_stock=Decimal("0"))

        ocr_patch, llm_patch = _mock_pipeline()
        with ocr_patch, llm_patch:
            upload = self.client.post(
                reverse("document-list-create"),
                {"image": make_test_image()},
                format="multipart",
                **self.headers,
            )
        self.document_id = upload.data["id"]

    def test_confirm_purchase_registers_it_and_updates_stock(self):
        response = self.client.post(
            reverse("document-confirm", kwargs={"document_id": self.document_id}),
            {
                "document_type": "purchase",
                "party_name": "Distribuidora ABC",
                "items": [
                    {"product_id": self.product.id, "quantity": "10", "unit_amount": "1000.00"}
                ],
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Purchase.objects.for_company(self.company).count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("10.000"))

        document = Document.objects.for_company(self.company).get(pk=self.document_id)
        self.assertEqual(document.status, Document.Status.CONFIRMED)
        self.assertIsNotNone(document.extraction.reviewed_by)
        self.assertIsNotNone(document.extraction.reviewed_at)

    def test_confirm_as_sale_calls_crear_venta(self):
        from sales.models import Sale

        self.product.current_stock = Decimal("50")
        self.product.save(update_fields=["current_stock"])

        response = self.client.post(
            reverse("document-confirm", kwargs={"document_id": self.document_id}),
            {
                "document_type": "sale",
                "party_name": "Cliente Y",
                "items": [
                    {"product_id": self.product.id, "quantity": "2", "unit_amount": "2500.00"}
                ],
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Sale.objects.for_company(self.company).count(), 1)

    def test_cannot_confirm_twice(self):
        payload = {
            "document_type": "purchase",
            "party_name": "Distribuidora ABC",
            "items": [{"product_id": self.product.id, "quantity": "1", "unit_amount": "1000.00"}],
        }
        self.client.post(
            reverse("document-confirm", kwargs={"document_id": self.document_id}),
            payload,
            format="json",
            **self.headers,
        )

        second = self.client.post(
            reverse("document-confirm", kwargs={"document_id": self.document_id}),
            payload,
            format="json",
            **self.headers,
        )

        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Purchase.objects.for_company(self.company).count(), 1)

    def test_reject_marks_document_rejected(self):
        response = self.client.post(
            reverse("document-reject", kwargs={"document_id": self.document_id}), **self.headers
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        document = Document.objects.for_company(self.company).get(pk=self.document_id)
        self.assertEqual(document.status, Document.Status.REJECTED)

    def test_cannot_confirm_a_rejected_document(self):
        self.client.post(
            reverse("document-reject", kwargs={"document_id": self.document_id}), **self.headers
        )

        response = self.client.post(
            reverse("document-confirm", kwargs={"document_id": self.document_id}),
            {
                "document_type": "purchase",
                "items": [{"product_id": self.product.id, "quantity": "1", "unit_amount": "1"}],
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Purchase.objects.for_company(self.company).count(), 0)

    def test_uploading_alone_never_creates_a_purchase(self):
        """Ver docs/SECURITY.md #7: nunca se registra nada solo por subir
        y procesar un documento — se necesita la confirmación explícita.
        """
        self.assertEqual(Purchase.objects.for_company(self.company).count(), 0)
        document = Document.objects.for_company(self.company).get(pk=self.document_id)
        self.assertEqual(document.status, Document.Status.NEEDS_REVIEW)


class DocumentIsolationTests(APITestCase):
    """Gate obligatorio de aislamiento multiempresa (docs/TESTING.md #2)."""

    def setUp(self):
        self.user_a = UserFactory()
        self.company_a = CompanyFactory()
        CompanyUserFactory(company=self.company_a, user=self.user_a, role=CompanyUser.Role.OWNER)
        self.client_a = APIClient()
        self.client_a.force_authenticate(self.user_a)

        self.company_b = CompanyFactory()
        user_b = UserFactory()
        CompanyUserFactory(company=self.company_b, user=user_b, role=CompanyUser.Role.OWNER)
        client_b = APIClient()
        client_b.force_authenticate(user_b)

        ocr_patch, llm_patch = _mock_pipeline()
        with ocr_patch, llm_patch:
            upload = client_b.post(
                reverse("document-list-create"),
                {"image": make_test_image()},
                format="multipart",
                **{COMPANY_HEADER: str(self.company_b.id)},
            )
        self.foreign_document_id = upload.data["id"]

    def test_cannot_list_foreign_documents(self):
        response = self.client_a.get(
            reverse("document-list-create"), **{COMPANY_HEADER: str(self.company_a.id)}
        )
        self.assertEqual(response.data, [])

    def test_cannot_retrieve_foreign_document(self):
        response = self.client_a.get(
            reverse("document-detail", kwargs={"pk": self.foreign_document_id}),
            **{COMPANY_HEADER: str(self.company_a.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_confirm_foreign_document(self):
        response = self.client_a.post(
            reverse("document-confirm", kwargs={"document_id": self.foreign_document_id}),
            {"document_type": "purchase", "items": []},
            format="json",
            **{COMPANY_HEADER: str(self.company_a.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_reject_foreign_document(self):
        response = self.client_a.post(
            reverse("document-reject", kwargs={"document_id": self.foreign_document_id}),
            **{COMPANY_HEADER: str(self.company_a.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
