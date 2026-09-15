from decimal import Decimal

from django.db.models import Sum

from catalog.services import consultar_stock_bajo
from core.dates import today_and_week_start
from sales.services import consultar_ventas

from .models import CashMovement


def _cash_period(company, since):
    queryset = CashMovement.objects.for_company(company).filter(created_at__gte=since)
    income = (
        queryset.filter(type=CashMovement.MovementType.INCOME).aggregate(total=Sum("amount"))[
            "total"
        ]
        or Decimal("0.00")
    )
    expense = (
        queryset.filter(type=CashMovement.MovementType.EXPENSE).aggregate(total=Sum("amount"))[
            "total"
        ]
        or Decimal("0.00")
    )
    return {
        "income": str(income),
        "expense": str(expense),
        "balance": str(income - expense),
    }


def obtener_resumen(*, company):
    """Tool Layer de solo lectura: fuente única de verdad para "cómo va el
    negocio hoy" (caja, ventas y stock bajo, hoy y esta semana). La usa el
    dashboard (Fase 6) y, sin cambios, el asistente conversacional en
    fases posteriores (ver docs/ROADMAP.md Fase 6 y Fase 8). Reutiliza
    `sales.consultar_ventas` y `catalog.consultar_stock_bajo` en vez de
    duplicar su lógica.
    """
    today_start, week_start = today_and_week_start()
    ventas = consultar_ventas(company=company)

    return {
        "cash": {
            "today": _cash_period(company, today_start),
            "week": _cash_period(company, week_start),
        },
        "sales": ventas,
        "low_stock_products": consultar_stock_bajo(company=company),
    }
