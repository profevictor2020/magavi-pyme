import json
from unittest import mock

from django.test import TestCase

from accounts.factories import UserFactory
from assistant.llm_providers import FakeLLMProvider
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory

from .image_test_helpers import make_test_image
from .models import Document, DocumentExtraction
from .ocr_providers import FakeOCRProvider
from .tasks import procesar_documento


class ProcesarDocumentoTests(TestCase):
    """Integration del pipeline completo: OCR -> estructuración -> queda
    en needs_review con datos razonables (ver docs/ROADMAP.md Fase 9).
    """

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory()
        self.product = ProductFactory(company=self.company, name="Café")
        self.document = Document.objects.create(
            company=self.company, uploaded_by=self.user, image=make_test_image()
        )

    def _run_with_fakes(self, ocr_text, llm_response):
        ocr_patch = mock.patch(
            "documents.tasks.get_ocr_provider", return_value=FakeOCRProvider(ocr_text)
        )
        llm_patch = mock.patch(
            "documents.structuring.get_llm_provider",
            return_value=FakeLLMProvider([llm_response]),
        )
        with ocr_patch, llm_patch:
            procesar_documento(self.document.id)

    def test_pipeline_ends_in_needs_review_with_structured_data(self):
        llm_response = json.dumps(
            {
                "document_type": "purchase",
                "counterparty_name": "Distribuidora ABC",
                "items": [
                    {
                        "product_id": self.product.id,
                        "product_name_raw": "CAFE",
                        "quantity": "10",
                        "unit_price": "1500",
                    }
                ],
                "total": "15000",
            }
        )

        self._run_with_fakes("FACTURA\nDistribuidora ABC\nCAFE x10 $1500", llm_response)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.NEEDS_REVIEW)
        self.assertEqual(self.document.document_type_guess, Document.DocumentType.PURCHASE)

        extraction = DocumentExtraction.objects.get(document=self.document)
        self.assertIn("Distribuidora ABC", extraction.raw_ocr_text)
        self.assertEqual(extraction.structured_data["counterparty_name"], "Distribuidora ABC")

    def test_pipeline_marks_failed_on_unexpected_error(self):
        with mock.patch(
            "documents.tasks.get_ocr_provider", side_effect=RuntimeError("motor OCR caído")
        ):
            with self.assertRaises(RuntimeError):
                procesar_documento(self.document.id)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.Status.FAILED)

    def test_unknown_document_id_is_a_noop(self):
        procesar_documento(999999)  # no debe lanzar
