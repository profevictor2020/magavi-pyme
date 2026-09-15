from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from companies.models import Company
from core.managers import CompanyScopedManager


class Conversation(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="conversations")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyScopedManager()

    def __str__(self):
        return f"Conversación #{self.pk} ({self.company})"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Usuario"
        ASSISTANT = "assistant", "Asistente"
        SYSTEM = "system", "Sistema"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    # El intent propuesto por el LLM antes de validar (Fase 8 en
    # adelante). Se guarda tal cual para poder auditar/depurar intentos
    # de abuso (ver docs/SECURITY.md #5).
    structured_intent = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"


class PendingAction(models.Model):
    """Máquina de estados de confirmación para operaciones mutantes
    propuestas por el asistente (ver docs/ARCHITECTURE.md #3.4 y
    docs/SECURITY.md #8). Vive en el backend, independiente de si la
    propuesta vino de un LLM (Fase 8) o de un JSON construido a mano
    (Fase 7): en ambos casos toda escritura pasa por aquí antes de
    tocar el Tool Layer real.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        CONFIRMED = "confirmed", "Confirmada"
        CANCELLED = "cancelled", "Cancelada"
        EXPIRED = "expired", "Expirada"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="pending_actions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pending_actions"
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        related_name="pending_actions",
        null=True,
        blank=True,
    )
    intent_name = models.CharField(max_length=50)
    # Los parámetros crudos (JSON-nativos) de la propuesta, no los ya
    # validados/convertidos: se vuelven a validar por completo al
    # confirmar, porque el estado del negocio pudo cambiar entre medio
    # (ver docs/ARCHITECTURE.md #3.4, "revalida al confirmar").
    parameters = models.JSONField(encoder=DjangoJSONEncoder)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    objects = CompanyScopedManager()

    class Meta:
        indexes = [
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self):
        return f"{self.intent_name} ({self.status})"
