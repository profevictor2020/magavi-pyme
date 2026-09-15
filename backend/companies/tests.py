from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.factories import UserFactory

from .factories import CompanyFactory, CompanyUserFactory
from .models import Company, CompanyUser


class CompanyCreateTests(APITestCase):
    def test_creating_company_makes_creator_owner(self):
        user = UserFactory()
        self.client.force_authenticate(user)

        response = self.client.post(
            reverse("company-list-create"), {"name": "Almacen Marcela", "rut": "76111111-1"}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        company = Company.objects.get(id=response.data["id"])
        membership = CompanyUser.objects.get(company=company, user=user)
        self.assertEqual(membership.role, CompanyUser.Role.OWNER)
        self.assertEqual(response.data["role"], CompanyUser.Role.OWNER)

    def test_create_company_requires_authentication(self):
        response = self.client.post(
            reverse("company-list-create"), {"name": "Sin sesion", "rut": "1-1"}
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rut_must_be_unique(self):
        CompanyFactory(rut="76222222-2")
        user = UserFactory()
        self.client.force_authenticate(user)

        response = self.client.post(
            reverse("company-list-create"), {"name": "Otra empresa", "rut": "76222222-2"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CompanyIsolationTests(APITestCase):
    """Gate obligatorio de aislamiento multiempresa (docs/SECURITY.md #4,
    docs/TESTING.md #2). Dos empresas con datos equivalentes; un usuario de
    una nunca debe ver ni acceder a datos de la otra.
    """

    def setUp(self):
        self.user_a = UserFactory()
        self.user_b = UserFactory()
        self.company_a = CompanyFactory()
        self.company_b = CompanyFactory()
        CompanyUserFactory(company=self.company_a, user=self.user_a, role=CompanyUser.Role.OWNER)
        CompanyUserFactory(company=self.company_b, user=self.user_b, role=CompanyUser.Role.OWNER)

    def test_user_only_lists_own_companies(self):
        self.client.force_authenticate(self.user_a)

        response = self.client.get(reverse("company-list-create"))

        ids = [c["id"] for c in response.data]
        self.assertIn(self.company_a.id, ids)
        self.assertNotIn(self.company_b.id, ids)

    def test_user_cannot_access_foreign_company_detail(self):
        self.client.force_authenticate(self.user_a)

        response = self.client.get(
            reverse("company-detail", kwargs={"company_id": self.company_b.id})
        )

        # 404, no 403: no debe confirmarse ni siquiera que la empresa existe.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_inactive_membership_loses_access(self):
        CompanyUser.objects.filter(company=self.company_a, user=self.user_a).update(
            is_active=False
        )
        self.client.force_authenticate(self.user_a)

        response = self.client.get(
            reverse("company-detail", kwargs={"company_id": self.company_a.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
