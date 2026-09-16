import json

from django.test import TestCase

from assistant.llm_providers import FakeLLMProvider
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory

from .structuring import estructurar_documento


class EstructurarDocumentoTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.product = ProductFactory(company=self.company, name="Café")

    def test_parses_a_valid_llm_response(self):
        raw = json.dumps(
            {
                "document_type": "purchase",
                "counterparty_name": "Distribuidora ABC",
                "date": "2026-09-15",
                "items": [
                    {
                        "product_id": self.product.id,
                        "product_name_raw": "CAFE MOLIDO",
                        "quantity": "20",
                        "unit_price": "1500",
                    }
                ],
                "total": "30000",
            }
        )
        llm = FakeLLMProvider([raw])

        resultado = estructurar_documento(
            company=self.company, raw_text="texto ocr", llm_provider=llm
        )

        self.assertEqual(resultado["document_type"], "purchase")
        self.assertEqual(resultado["counterparty_name"], "Distribuidora ABC")
        self.assertEqual(len(resultado["items"]), 1)
        self.assertEqual(resultado["items"][0]["product_id"], self.product.id)

    def test_invalid_llm_response_returns_empty_structure(self):
        llm = FakeLLMProvider(["esto no es json"])

        resultado = estructurar_documento(
            company=self.company, raw_text="texto ocr", llm_provider=llm
        )

        self.assertEqual(resultado["document_type"], "unknown")
        self.assertEqual(resultado["items"], [])

    def test_item_without_confident_match_has_null_product_id(self):
        raw = json.dumps(
            {
                "document_type": "purchase",
                "items": [
                    {
                        "product_id": None,
                        "product_name_raw": "PRODUCTO DESCONOCIDO",
                        "quantity": "5",
                        "unit_price": "1000",
                    }
                ],
            }
        )
        llm = FakeLLMProvider([raw])

        resultado = estructurar_documento(
            company=self.company, raw_text="texto ocr", llm_provider=llm
        )

        self.assertIsNone(resultado["items"][0]["product_id"])
