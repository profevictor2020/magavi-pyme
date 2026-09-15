from decimal import Decimal

from django.db.models import Count, F, Sum

from catalog.models import Product
from core.dates import today_and_week_start
from sales.models import Sale

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


def _sales_period(company, since):
    aggregate = (
        Sale.objects.for_company(company)
        .filter(status=Sale.Status.CONFIRMED, sold_at__gte=since)
        .aggregate(total=Sum("total"), count=Count("id"))
    )
    return {
        "total": str(aggregate["total"] or Decimal("0.00")),
        "count": aggregate["count"] or 0,
    }


def _low_stock_products(company):
    products = (
        Product.objects.for_company(company)
        .filter(is_active=True, current_stock__lte=F("low_stock_threshold"))
        .order_by("name")
    )
    return [
        {
            "id": product.id,
            "name": product.name,
            "current_stock": str(product.current_stock),
            "low_stock_threshold": str(product.low_stock_threshold),
        }
        for product in products
    ]


def obtener_resumen(*, company):
    """Tool Layer de solo lectura: fuente única de verdad para "cómo va el
    negocio hoy" (caja, ventas y stock bajo, hoy y esta semana). La usa el
    dashboard (Fase 6) y, sin cambios, el asistente conversacional en
    fases posteriores (ver docs/ROADMAP.md Fase 6 y Fase 8).
    """
    today_start, week_start = today_and_week_start()

    return {
        "cash": {
            "today": _cash_period(company, today_start),
            "week": _cash_period(company, week_start),
        },
        "sales": {
            "today": _sales_period(company, today_start),
            "week": _sales_period(company, week_start),
        },
        "low_stock_products": _low_stock_products(company),
    }
