from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.factories import UserFactory
from catalog.factories import ProductFactory
from companies.factories import CompanyFactory, CompanyUserFactory
from companies.models import CompanyUser
from sales.services import crear_venta

COMPANY_HEADER = "HTTP_X_COMPANY_ID"


class CashboxSummaryAPITests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user)
        self.headers = {COMPANY_HEADER: str(self.company.id)}

    def test_summary_matches_data_loaded_in_previous_phases(self):
        product = ProductFactory(
            company=self.company,
            default_price=Decimal("2500.00"),
            current_stock=Decimal("3"),
            low_stock_threshold=Decimal("5"),
        )
        crear_venta(
            company=self.company,
            user=self.user,
            items=[{"product": product, "quantity": Decimal("1")}],
        )

        response = self.client.get(reverse("cashbox-summary"), **self.headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cash"]["today"]["income"], "2500.00")
        self.assertEqual(response.data["sales"]["today"]["total"], "2500.00")
        names = [p["name"] for p in response.data["low_stock_products"]]
        self.assertIn(product.name, names)

    def test_requires_company_header(self):
        response = self.client.get(reverse("cashbox-summary"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.get(reverse("cashbox-summary"), **self.headers)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CashboxSummaryIsolationTests(APITestCase):
    """Gate obligatorio de aislamiento multiempresa (docs/TESTING.md #2)."""

    def setUp(self):
        self.user_a = UserFactory()
        self.company_a = CompanyFactory()
        CompanyUserFactory(company=self.company_a, user=self.user_a, role=CompanyUser.Role.OWNER)
        self.client.force_authenticate(self.user_a)

        self.company_b = CompanyFactory()
        user_b = UserFactory()
        CompanyUserFactory(company=self.company_b, user=user_b, role=CompanyUser.Role.OWNER)
        product_b = ProductFactory(
            company=self.company_b, current_stock=Decimal("1"), low_stock_threshold=Decimal("5")
        )
        crear_venta(
            company=self.company_b,
            user=user_b,
            items=[{"product": product_b, "quantity": Decimal("0.5")}],
        )

    def test_summary_does_not_leak_other_company_data(self):
        response = self.client.get(
            reverse("cashbox-summary"), **{COMPANY_HEADER: str(self.company_a.id)}
        )

        self.assertEqual(
            response.data["cash"]["today"],
            {"income": "0.00", "expense": "0.00", "balance": "0.00"},
        )
        self.assertEqual(response.data["sales"]["today"], {"total": "0.00", "count": 0})
        self.assertEqual(response.data["low_stock_products"], [])

    def test_cannot_use_foreign_company_header(self):
        response = self.client.get(
            reverse("cashbox-summary"), **{COMPANY_HEADER: str(self.company_b.id)}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
