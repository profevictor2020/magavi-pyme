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
