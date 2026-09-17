import datetime

from django.utils import timezone


def today_and_week_start():
    """Devuelve (inicio_de_hoy, inicio_de_semana) en la zona horaria local
    (America/Santiago, ver config/settings.py TIME_ZONE). Usado por los
    resúmenes de ventas/compras/caja para que "hoy" y "esta semana" sean
    correctos para el negocio, no arbitrariamente en UTC.
    """
    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timezone.timedelta(days=today_start.weekday())
    return today_start, week_start


# Períodos con nombre que el asistente puede pedir sin necesitar saber la
# fecha de hoy — el cálculo real vive acá, en el servidor (igual que
# today_and_week_start ya hacía para "hoy"/"semana"), nunca en lo que el
# LLM calcule por su cuenta (ver docs/DECISIONS.md ADR-022).
PERIOD_CHOICES = ("hoy", "semana", "mes", "anio", "total")


def resolve_period_range(
    period: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
) -> tuple[timezone.datetime | None, timezone.datetime | None]:
    """Devuelve (inicio, fin) en la zona horaria local para filtrar una
    consulta histórica (gastos, ventas) — ver ADR-022. `fin` es EXCLUSIVO
    (el día siguiente a las 00:00) para incluir el día completo de
    `date_to`/"hoy" sin depender de la hora exacta del registro.

    Un rango explícito (date_from/date_to) tiene prioridad sobre `period`
    — así "gastos de agosto" (que el modelo traduce a fechas concretas
    usando la fecha de hoy que se le da en el contexto, ver
    _construir_contexto_fecha) funciona igual que "gastos de este mes"
    (period="mes", resuelto acá sin que el modelo tenga que calcular
    nada). (None, None) — sin período ni rango, o period="total" — no
    filtra: trae todo el histórico.
    """
    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if date_from is not None or date_to is not None:
        inicio = (
            timezone.make_aware(datetime.datetime.combine(date_from, datetime.time.min))
            if date_from
            else None
        )
        fin = (
            timezone.make_aware(datetime.datetime.combine(date_to, datetime.time.min))
            + datetime.timedelta(days=1)
            if date_to
            else None
        )
        return inicio, fin

    if period == "hoy":
        return today_start, today_start + datetime.timedelta(days=1)
    if period == "semana":
        return today_start - datetime.timedelta(days=today_start.weekday()), None
    if period == "mes":
        return today_start.replace(day=1), None
    if period == "anio":
        return today_start.replace(month=1, day=1), None

    # period == "total" o None: todo el histórico, sin filtrar.
    return None, None
