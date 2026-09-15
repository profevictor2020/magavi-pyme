from rest_framework.exceptions import NotFound, ValidationError

from companies.models import CompanyUser

COMPANY_HEADER = "X-Company-Id"


def get_current_company(request):
    """Resuelve la empresa activa a partir del usuario autenticado y el
    header X-Company-Id, validando membresía activa.

    Nunca confía en un company_id que venga del body/query sin pasar por
    esta validación (ver docs/SECURITY.md #3). Devuelve 404 (no 403) ante
    una empresa ajena, para no confirmar su existencia (IDOR).
    """
    company_id = request.headers.get(COMPANY_HEADER)
    if not company_id:
        raise ValidationError({"detail": f"Falta el header {COMPANY_HEADER}."})

    membership = (
        CompanyUser.objects.select_related("company")
        .filter(company_id=company_id, user=request.user, is_active=True)
        .first()
    )
    if membership is None:
        raise NotFound()

    return membership.company
