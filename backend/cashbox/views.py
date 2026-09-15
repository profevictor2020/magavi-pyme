from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import get_current_company

from .services import obtener_resumen


class CashboxSummaryView(APIView):
    """Fuente única de verdad para el dashboard: caja, ventas y stock bajo
    de hoy y de la semana (ver docs/ROADMAP.md Fase 6).
    """

    def get(self, request):
        company = get_current_company(request)
        return Response(obtener_resumen(company=company))
