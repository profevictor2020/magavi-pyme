import factory

from .models import Company, CompanyModule, CompanyUser, Module


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company

    name = factory.Sequence(lambda n: f"Empresa {n}")
    rut = factory.Sequence(lambda n: f"{76000000 + n}-{n % 10}")


class CompanyUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CompanyUser

    company = factory.SubFactory(CompanyFactory)
    user = factory.SubFactory("accounts.factories.UserFactory")
    role = CompanyUser.Role.STAFF


class ModuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Module

    code = factory.Sequence(lambda n: f"module-{n}")
    name = factory.Sequence(lambda n: f"Modulo {n}")


class CompanyModuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CompanyModule

    company = factory.SubFactory(CompanyFactory)
    module = factory.SubFactory(ModuleFactory)
