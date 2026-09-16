"""Rate limiting (ver docs/SECURITY.md #9): protege login/refresh contra
fuerza bruta y el asistente/documentos contra abuso de recursos (costo
de inferencia LLM + OCR).
"""

from rest_framework.throttling import ScopedRateThrottle


class CompanyScopedRateThrottle(ScopedRateThrottle):
    """Como `ScopedRateThrottle` (límite por usuario autenticado, o por IP
    si es anónimo), pero además separa el balde por empresa activa
    (`X-Company-Id`) cuando está presente. Así el límite es "por usuario
    Y por empresa": dos empresas distintas administradas por el mismo
    usuario no comparten cupo, y el abuso desde una empresa no consume el
    cupo de otra.
    """

    def get_cache_key(self, request, view):
        base_key = super().get_cache_key(request, view)
        if base_key is None:
            return None
        company_id = request.headers.get("X-Company-Id", "-")
        return f"{base_key}:company={company_id}"
