from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.factories import UserFactory
from companies.factories import CompanyFactory, CompanyUserFactory
from companies.models import CompanyUser

from .factories import ProductFactory
from .models import Product

COMPANY_HEADER = "HTTP_X_COMPANY_ID"


class ProductCRUDTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user)
        self.headers = {COMPANY_HEADER: str(self.company.id)}

    def test_create_product_requires_company_header(self):
        response = self.client.post(
            reverse("product-list"), {"name": "Cafe"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_sets_company_from_header(self):
        response = self.client.post(
            reverse("product-list"),
            {"name": "Cafe", "default_price": "2500.00"},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        product = Product.objects.for_company(self.company).get(id=response.data["id"])
        self.assertEqual(product.name, "Cafe")
        self.assertEqual(product.current_stock, Decimal("0.000"))

    def test_create_product_with_initial_stock_creates_movement(self):
        response = self.client.post(
            reverse("product-list"),
            {"name": "Azucar", "initial_stock": "20"},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data["current_stock"]), Decimal("20.000"))

    def test_duplicate_sku_in_same_company_rejected(self):
        ProductFactory(company=self.company, sku="ABC-1")

        response = self.client.post(
            reverse("product-list"),
            {"name": "Otro", "sku": "ABC-1"},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_sku_allowed_in_different_company(self):
        other_company = CompanyFactory()
        ProductFactory(company=other_company, sku="ABC-1")

        response = self.client.post(
            reverse("product-list"),
            {"name": "Otro", "sku": "ABC-1"},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update_product(self):
        product = ProductFactory(company=self.company, name="Original")

        response = self.client.patch(
            reverse("product-detail", kwargs={"pk": product.id}),
            {"name": "Actualizado"},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertEqual(product.name, "Actualizado")

    def test_delete_not_allowed(self):
        product = ProductFactory(company=self.company)

        response = self.client.delete(
            reverse("product-detail", kwargs={"pk": product.id}), **self.headers
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class ProductIsolationTests(APITestCase):
    """Gate obligatorio de aislamiento multiempresa (docs/TESTING.md #2)."""

    def setUp(self):
        self.user_a = UserFactory()
        self.company_a = CompanyFactory()
        CompanyUserFactory(company=self.company_a, user=self.user_a, role=CompanyUser.Role.OWNER)

        self.company_b = CompanyFactory()
        self.product_b = ProductFactory(company=self.company_b, name="Producto de B")

        self.client.force_authenticate(self.user_a)

    def test_cannot_list_products_of_foreign_company(self):
        ProductFactory(company=self.company_a, name="Producto de A")

        response = self.client.get(
            reverse("product-list"), **{COMPANY_HEADER: str(self.company_a.id)}
        )

        names = [p["name"] for p in response.data]
        self.assertIn("Producto de A", names)
        self.assertNotIn("Producto de B", names)

    def test_cannot_retrieve_foreign_product_even_with_own_company_header(self):
        response = self.client.get(
            reverse("product-detail", kwargs={"pk": self.product_b.id}),
            **{COMPANY_HEADER: str(self.company_a.id)},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_use_foreign_company_header(self):
        response = self.client.get(
            reverse("product-list"), **{COMPANY_HEADER: str(self.company_b.id)}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_adjust_stock_of_foreign_product(self):
        response = self.client.post(
            reverse("product-adjust-stock", kwargs={"pk": self.product_b.id}),
            {"cantidad": "5", "motivo": "intento cruzado"},
            format="json",
            **{COMPANY_HEADER: str(self.company_a.id)},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class LowStockAndAdjustStockTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user)
        self.headers = {COMPANY_HEADER: str(self.company.id)}

    def test_low_stock_filter(self):
        ProductFactory(
            company=self.company,
            name="Bajo stock",
            current_stock=Decimal("1"),
            low_stock_threshold=Decimal("5"),
        )
        ProductFactory(
            company=self.company,
            name="Stock ok",
            current_stock=Decimal("50"),
            low_stock_threshold=Decimal("5"),
        )

        response = self.client.get(reverse("product-list"), {"low_stock": "true"}, **self.headers)

        names = [p["name"] for p in response.data]
        self.assertIn("Bajo stock", names)
        self.assertNotIn("Stock ok", names)

    def test_adjust_stock_endpoint_updates_product(self):
        product = ProductFactory(company=self.company, current_stock=Decimal("10"))

        response = self.client.post(
            reverse("product-adjust-stock", kwargs={"pk": product.id}),
            {"cantidad": "-3", "motivo": "Venta mostrador"},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        product.refresh_from_db()
        self.assertEqual(product.current_stock, Decimal("7.000"))

    def test_adjust_stock_rejects_negative_result(self):
        product = ProductFactory(company=self.company, current_stock=Decimal("2"))

        response = self.client.post(
            reverse("product-adjust-stock", kwargs={"pk": product.id}),
            {"cantidad": "-10", "motivo": "Excesivo"},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
