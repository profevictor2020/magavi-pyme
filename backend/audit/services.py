from .models import AuditLog


def registrar_auditoria(
    *, company, user, action, entity_type, entity_id, after=None, before=None, source="api"
):
    """Escribe una entrada de auditoría. Instrumentación completa de todos
    los flujos de escritura es Fase 11; por ahora la usan los Tool Layer
    que ya se van construyendo (crear_venta en Fase 4 en adelante).
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
