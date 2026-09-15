from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .intents import INTENTS, ejecutar_intent
from .models import PendingAction

CONFIRMATION_TIMEOUT = timedelta(minutes=10)


def proponer_intent(*, company, user, intent_name, raw_parameters, conversation=None):
    """Valida la forma de un intent (ver docs/ARCHITECTURE.md #3.4).

    Si es de solo lectura, se ejecuta de inmediato. Si es mutante, se
    crea una propuesta pendiente de confirmación en vez de ejecutar
    nada — ninguna operación de escritura ocurre en este paso.
    """
    definition = INTENTS.get(intent_name)
    if definition is None:
        raise ValidationError(f"Intent desconocido: {intent_name}")

    serializer = definition.parameter_serializer(data=raw_parameters)
    serializer.is_valid(raise_exception=True)

    if not definition.requires_confirmation:
        resultado = ejecutar_intent(
            company=company,
            user=user,
            intent_name=intent_name,
            validated_params=serializer.validated_data,
        )
        return {"status": "executed", "result": resultado}

    pending = PendingAction.objects.create(
        company=company,
        user=user,
        conversation=conversation,
        intent_name=intent_name,
        # Se guardan los parámetros crudos, no los ya validados: se
        # vuelven a validar por completo al confirmar.
        parameters=raw_parameters,
        expires_at=timezone.now() + CONFIRMATION_TIMEOUT,
    )
    return {
        "status": "pending_confirmation",
        "pending_action_id": pending.id,
        "intent": intent_name,
        "parameters": pending.parameters,
        "expires_at": pending.expires_at,
    }


def _get_own_pending_action(*, company, user, pending_action_id):
    pending = (
        PendingAction.objects.for_company(company)
        .select_for_update()
        .filter(pk=pending_action_id, user=user)
        .first()
    )
    if pending is None:
        raise ValidationError("Propuesta no encontrada.")
    return pending


def confirmar_intent(*, company, user, pending_action_id):
    """Ejecuta de verdad una propuesta pendiente, revalidándola por
    completo primero (el estado del negocio pudo cambiar desde que se
    propuso: precio, stock, etc. — ver docs/SECURITY.md #8).

    Si la ejecución falla (p.ej. ya no hay stock suficiente), la
    propuesta queda igual que antes (sigue "pending" hasta que expire o
    se cancele): no se marca confirmada ni se pierde el registro.
    """
    expired = False
    resultado = None

    with transaction.atomic():
        pending = _get_own_pending_action(
            company=company, user=user, pending_action_id=pending_action_id
        )

        if pending.status != PendingAction.Status.PENDING:
            raise ValidationError(f"La propuesta ya fue {pending.get_status_display().lower()}.")

        if pending.expires_at < timezone.now():
            # Se guarda el estado "expired" y SE SALE del bloque atómico
            # sin excepción, para que el guardado no se revierta; la
            # excepción se lanza después (ver más abajo). Si se lanzara
            # aquí dentro, transaction.atomic() revertiría también el
            # guardado de este mismo estado.
            pending.status = PendingAction.Status.EXPIRED
            pending.resolved_at = timezone.now()
            pending.save(update_fields=["status", "resolved_at"])
            expired = True
        else:
            definition = INTENTS[pending.intent_name]
            serializer = definition.parameter_serializer(data=pending.parameters)
            serializer.is_valid(raise_exception=True)

            resultado = ejecutar_intent(
                company=company,
                user=user,
                intent_name=pending.intent_name,
                validated_params=serializer.validated_data,
            )

            pending.status = PendingAction.Status.CONFIRMED
            pending.resolved_at = timezone.now()
            pending.save(update_fields=["status", "resolved_at"])

    if expired:
        raise ValidationError("La propuesta expiró; vuelve a intentarlo.")

    return resultado


def cancelar_intent(*, company, user, pending_action_id):
    with transaction.atomic():
        pending = _get_own_pending_action(
            company=company, user=user, pending_action_id=pending_action_id
        )

        if pending.status != PendingAction.Status.PENDING:
            raise ValidationError(f"La propuesta ya fue {pending.get_status_display().lower()}.")

        pending.status = PendingAction.Status.CANCELLED
        pending.resolved_at = timezone.now()
        pending.save(update_fields=["status", "resolved_at"])

    return pending
