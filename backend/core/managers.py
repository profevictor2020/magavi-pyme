from django.db import models


class MissingCompanyScopeError(Exception):
    """Se evaluó un queryset de un modelo con scope de empresa sin pasar por
    for_company(company) explícito.

    Ver docs/ARCHITECTURA.md #4 y docs/SECURITY.md #4: un query sin filtro
    de empresa debe fallar en vez de devolver datos de todas las empresas.
    """


class CompanyScopedQuerySet(models.QuerySet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._company_scoped = False

    def for_company(self, company):
        clone = self.filter(company=company)
        clone._company_scoped = True
        return clone

    def _clone(self):
        clone = super()._clone()
        clone._company_scoped = self._company_scoped
        return clone

    def _fetch_all(self):
        if not self._company_scoped and self._result_cache is None:
            raise MissingCompanyScopeError(
                f"Query sobre {self.model.__name__} sin .for_company(company) explícito. "
                "Nunca uses .objects.all()/.filter() directo en un modelo con scope de "
                "empresa; usa Modelo.objects.for_company(company)."
            )
        super()._fetch_all()


CompanyScopedManager = models.Manager.from_queryset(CompanyScopedQuerySet)
