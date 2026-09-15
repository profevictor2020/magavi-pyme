from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.factories import UserFactory
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory, CompanyUserFactory
from companies.models import CompanyUser

from .services import crear_venta

COMPANY_HEADER = "HTTP_X_COMPANY_ID"


class SaleCreateAPITests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user)
        self.headers = {COMPANY_HEADER: str(self.company.id)}
        self.product = ProductFactory(
            company=self.company, default_price=Decimal("2500.00"), current_stock=Decimal("10")
        )

    def test_create_sale(self):
        response = self.client.post(
            reverse("sale-list-create"),
            {"items": [{"product_id": self.product.id, "quantity": "3"}]},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total"], "7500.00")
        self.assertEqual(len(response.data["items"]), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("7.000"))

    def test_create_sale_requires_items(self):
        response = self.client.post(
            reverse("sale-list-create"), {"items": []}, format="json", **self.headers
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_sale_requires_company_header(self):
        response = self.client.post(
            reverse("sale-list-create"),
            {"items": [{"product_id": self.product.id, "quantity": "1"}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_sale_with_insufficient_stock_returns_400(self):
        response = self.client.post(
            reverse("sale-list-create"),
            {"items": [{"product_id": self.product.id, "quantity": "999"}]},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("10.000"))

    def test_create_sale_with_foreign_product_returns_404(self):
        other_company = CompanyFactory()
        foreign_product = ProductFactory(company=other_company)

        response = self.client.post(
            reverse("sale-list-create"),
            {"items": [{"product_id": foreign_product.id, "quantity": "1"}]},
            format="json",
            **self.headers,
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_sales(self):
        self.client.post(
            reverse("sale-list-create"),
            {"items": [{"product_id": self.product.id, "quantity": "1"}]},
            format="json",
            **self.headers,
        )

        response = self.client.get(reverse("sale-list-create"), **self.headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class SaleSummaryTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user)
        self.headers = {COMPANY_HEADER: str(self.company.id)}
        self.product = ProductFactory(
            company=self.company, default_price=Decimal("1000.00"), current_stock=Decimal("100")
        )

    def test_summary_reflects_todays_sale(self):
        self.client.post(
            reverse("sale-list-create"),
            {"items": [{"product_id": self.product.id, "quantity": "2"}]},
            format="json",
            **self.headers,
        )

        response = self.client.get(reverse("sale-summary"), **self.headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["today"]["total"], "2000.00")
        self.assertEqual(response.data["today"]["count"], 1)
        self.assertEqual(response.data["week"]["total"], "2000.00")

    def test_summary_with_no_sales_is_zero(self):
        response = self.client.get(reverse("sale-summary"), **self.headers)

        self.assertEqual(response.data["today"], {"total": "0.00", "count": 0})


class SaleIsolationTests(APITestCase):
    """Gate obligatorio de aislamiento multiempresa (docs/TESTING.md #2)."""

    def setUp(self):
        self.user_a = UserFactory()
        self.company_a = CompanyFactory()
        CompanyUserFactory(company=self.company_a, user=self.user_a, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user_a)

        self.company_b = CompanyFactory()
        user_b = UserFactory()
        CompanyUserFactory(company=self.company_b, user=user_b, role=CompanyUser.Role.OWNER)
        product_b = ProductFactory(company=self.company_b, current_stock=Decimal("10"))
        crear_venta(
            company=self.company_b,
            user=user_b,
            items=[{"product": product_b, "quantity": Decimal("1")}],
        )

    def test_sales_of_other_company_not_listed(self):
        response = self.client.get(
            reverse("sale-list-create"), **{COMPANY_HEADER: str(self.company_a.id)}
        )

        self.assertEqual(response.data, [])

    def test_cannot_use_foreign_company_header(self):
        response = self.client.get(
            reverse("sale-list-create"), **{COMPANY_HEADER: str(self.company_b.id)}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_summary_isolated_per_company(self):
        response = self.client.get(
            reverse("sale-summary"), **{COMPANY_HEADER: str(self.company_a.id)}
        )

        self.assertEqual(response.data["today"], {"total": "0.00", "count": 0})
