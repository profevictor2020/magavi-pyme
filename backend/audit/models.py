from django.conf import settings
from django.db import models

from companies.models import Company


class AuditLog(models.Model):
    """Registro append-only de operaciones relevantes (ver docs/SECURITY.md
    #10). No usa CompanyScopedManager: a diferencia del resto de los
    modelos de negocio, un AuditLog puede no tener empresa (eventos de
    sistema) y su superficie de consulta se diseña completa en Fase 11.
    Por ahora solo se escribe desde el Tool Layer, no se expone por API.
    """

    class Source(models.TextChoices):
        UI = "ui", "UI"
        ASSISTANT = "assistant", "Asistente"
        DOCUMENT = "document", "Documento"
        API = "api", "API"
        SYSTEM = "system", "Sistema"

    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.API)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id}"
