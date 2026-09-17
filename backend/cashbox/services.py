from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from audit.services import audit_source_for_origen, registrar_auditoria
from catalog.services import consultar_stock_bajo
from core.dates import resolve_period_range, today_and_week_start
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


def get_cash_movement_or_raise(*, company, cash_movement_id):
    """Resuelve un cash_movement_id a una instancia CashMovement con
    scope de empresa (mismo patrón que catalog.get_product_or_raise),
    para el Tool Layer del asistente."""
    movement = CashMovement.objects.for_company(company).filter(pk=cash_movement_id).first()
    if movement is None:
        raise ValidationError(f"El movimiento {cash_movement_id} no existe en esta empresa.")
    return movement


def actualizar_gasto(
    *, company, user, cash_movement, amount=None, category=None, description=None, origen="manual"
):
    """Tool Layer: corrige un egreso manual ya registrado (ver
    docs/DECISIONS.md ADR-019) — para cuando el usuario se equivoca al
    registrar un gasto (monto, categoría o descripción). Solo aplica a
    egresos manuales (reference_type=MANUAL): un CashMovement generado
    automáticamente por una venta o compra no se "corrige" acá, se
    corrige anulando/rehaciendo esa venta o compra.
    """
    if cash_movement.reference_type != CashMovement.ReferenceType.MANUAL:
        raise ValidationError(
            "Solo se pueden corregir egresos manuales, no los generados por una venta o compra."
        )

    changes = {}
    if amount is not None:
        amount = Decimal(amount)
        if amount <= 0:
            raise ValidationError("El monto del gasto debe ser mayor a cero.")
        changes["amount"] = amount
    if category is not None:
        changes["category"] = category
    if description is not None:
        changes["description"] = description
    if not changes:
        raise ValidationError("No se indicó ningún campo para actualizar.")

    categoria_final = changes.get("category", cash_movement.category)
    descripcion_final = changes.get("description", cash_movement.description)
    if categoria_final == CashMovement.Category.OTRO and not descripcion_final:
        raise ValidationError('Los gastos de categoría "otro" necesitan una descripción.')

    before = {field: str(getattr(cash_movement, field)) for field in changes}

    with transaction.atomic():
        for field, value in changes.items():
            setattr(cash_movement, field, value)
        cash_movement.save(update_fields=list(changes))

        registrar_auditoria(
            company=company,
            user=user,
            action="cashmovement.update",
            entity_type="CashMovement",
            entity_id=cash_movement.id,
            before=before,
            after={field: str(value) for field, value in changes.items()},
            source=audit_source_for_origen(origen),
        )

    return cash_movement


def consultar_gastos(*, company, period=None, date_from=None, date_to=None, limit=200):
    """Tool Layer de solo lectura: egresos manuales registrados (ver
    registrar_gasto), más recientes primero — "¿qué gastos llevamos?",
    "muéstrame los gastos". No incluye compras de inventario a
    proveedores (eso es otro concepto, con su propio registro en
    Purchase) ni ingresos de ventas.

    Sin period ni date_from/date_to, no filtra por fecha (todo el
    histórico manual, hasta `limit`) — igual que antes de ADR-022. Con
    period ("hoy"/"semana"/"mes"/"anio"/"total") o un rango explícito
    (date_from/date_to), acota a ese período — ver
    core.dates.resolve_period_range. `limit` subió de 50 a 200 al
    agregar filtrado por fecha: antes ser "los últimos 50" alcanzaba
    para cubrir "este mes" por accidente (pocos gastos manuales en la
    práctica); ahora que el período es explícito, no hay que confiar en
    ese accidente.
    """
    inicio, fin = resolve_period_range(period, date_from, date_to)
    queryset = CashMovement.objects.for_company(company).filter(
        type=CashMovement.MovementType.EXPENSE,
        reference_type=CashMovement.ReferenceType.MANUAL,
    )
    if inicio is not None:
        queryset = queryset.filter(created_at__gte=inicio)
    if fin is not None:
        queryset = queryset.filter(created_at__lt=fin)
    movimientos = queryset.order_by("-created_at")[:limit]
    return [
        {
            "id": m.id,
            "category": m.category,
            "description": m.description,
            "amount": str(m.amount),
            "created_at": m.created_at.isoformat(),
        }
        for m in movimientos
    ]


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
