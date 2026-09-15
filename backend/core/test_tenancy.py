from django.test import RequestFactory, TestCase
from rest_framework.exceptions import NotFound, ValidationError

from accounts.factories import UserFactory
from companies.factories import CompanyFactory, CompanyUserFactory
from companies.models import CompanyUser

from .tenancy import get_current_company


class GetCurrentCompanyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.company = CompanyFactory()
        CompanyUserFactory(company=self.company, user=self.user, role=CompanyUser.Role.OWNER)

    def _request(self, headers=None):
        request = self.factory.get("/", **(headers or {}))
        request.user = self.user
        return request

    def test_returns_company_for_valid_membership(self):
        request = self._request({"HTTP_X_COMPANY_ID": str(self.company.id)})

        company = get_current_company(request)

        self.assertEqual(company.id, self.company.id)

    def test_missing_header_raises_validation_error(self):
        request = self._request()

        with self.assertRaises(ValidationError):
            get_current_company(request)

    def test_foreign_company_raises_not_found(self):
        other_company = CompanyFactory()
        request = self._request({"HTTP_X_COMPANY_ID": str(other_company.id)})

        with self.assertRaises(NotFound):
            get_current_company(request)

    def test_inactive_membership_raises_not_found(self):
        CompanyUser.objects.filter(company=self.company, user=self.user).update(is_active=False)
        request = self._request({"HTTP_X_COMPANY_ID": str(self.company.id)})

        with self.assertRaises(NotFound):
            get_current_company(request)
