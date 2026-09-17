from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from audit.services import audit_source_for_origen, registrar_auditoria
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


def registrar_gasto(*, company, user, amount, category, description="", origen="manual"):
    """Tool Layer: único punto de escritura para egresos que NO son
    compra de inventario (arriendo, sueldos, servicios, u otro gasto
    puntual) — ver docs/DECISIONS.md ADR-018. A diferencia de
    registrar_compra (purchases/services.py), no toca stock ni
    productos: es plata que sale de la caja sin más, así que solo crea
    el CashMovement directo.
    """
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError("El monto del gasto debe ser mayor a cero.")
    if category == CashMovement.Category.OTRO and not description:
        raise ValidationError('Los gastos de categoría "otro" necesitan una descripción.')

    with transaction.atomic():
        movement = CashMovement.objects.create(
            company=company,
            type=CashMovement.MovementType.EXPENSE,
            amount=amount,
            reference_type=CashMovement.ReferenceType.MANUAL,
            category=category,
            description=description,
            created_by=user,
        )
        registrar_auditoria(
            company=company,
            user=user,
            action="cashmovement.create",
            entity_type="CashMovement",
            entity_id=movement.id,
            after={"amount": str(amount), "category": category, "description": description},
            source=audit_source_for_origen(origen),
        )

    return movement


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
