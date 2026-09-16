from .models import AuditLog

# Los Tool Layer usan `origen` con su propio vocabulario ("manual",
# "assistant", "document" — ver Sale.source/Purchase.source) mientras que
# `AuditLog.source` tiene un choices field más estricto (ver
# docs/DATA_MODEL.md). Este mapeo evita que cada Tool Layer necesite
# conocer el vocabulario de auditoría.
_ORIGEN_TO_AUDIT_SOURCE = {
    "manual": AuditLog.Source.UI,
    "assistant": AuditLog.Source.ASSISTANT,
    "document": AuditLog.Source.DOCUMENT,
}


def audit_source_for_origen(origen: str) -> str:
    return _ORIGEN_TO_AUDIT_SOURCE.get(origen, AuditLog.Source.API)


def registrar_auditoria(
    *, company, user, action, entity_type, entity_id, after=None, before=None, source="api"
):
    """Escribe una entrada de auditoría (ver docs/SECURITY.md #10:
    instrumentación completa de todos los flujos de escritura relevantes
    — Sale/Purchase/InventoryMovement, confirmación de documentos,
    login/logout/registro, creación de empresa).
    """
    return AuditLog.objects.create(
        company=company,
        user=user,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before=before,
        after=after,
        source=source,
    )
