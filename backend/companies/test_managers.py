from django.test import TestCase

from core.managers import MissingCompanyScopeError

from .factories import CompanyFactory, CompanyModuleFactory, ModuleFactory
from .models import CompanyModule


class CompanyScopedManagerTests(TestCase):
    """Prueba la pieza central del aislamiento multiempresa a nivel de ORM
    (docs/ARCHITECTURE.md #4): un query sin .for_company() debe fallar, no
    devolver datos de todas las empresas.
    """

    def test_for_company_returns_only_that_companys_rows(self):
        company_a = CompanyFactory()
        company_b = CompanyFactory()
        module = ModuleFactory()
        CompanyModuleFactory(company=company_a, module=module)
        CompanyModuleFactory(company=company_b, module=module)

        result = list(CompanyModule.objects.for_company(company_a))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].company_id, company_a.id)

    def test_query_without_for_company_raises(self):
        with self.assertRaises(MissingCompanyScopeError):
            list(CompanyModule.objects.all())

    def test_chaining_after_for_company_stays_scoped(self):
        company = CompanyFactory()
        module = ModuleFactory()
        CompanyModuleFactory(company=company, module=module, enabled=True)

        result = list(CompanyModule.objects.for_company(company).filter(enabled=True))

        self.assertEqual(len(result), 1)
