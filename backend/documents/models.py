import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from companies.models import Company
from core.managers import CompanyScopedManager


def _document_upload_path(instance, filename):
    # Nombre aleatorio, no el original (ver docs/SECURITY.md #6): evita
    # colisiones y no expone nada del nombre que subió el usuario.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"documents/{instance.company_id}/{uuid.uuid4().hex}.{ext}"


class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Subido"
        PROCESSING = "processing", "Procesando"
        NEEDS_REVIEW = "needs_review", "Necesita revisión"
        CONFIRMED = "confirmed", "Confirmado"
        REJECTED = "rejected", "Rechazado"
        FAILED = "failed", "Falló el procesamiento"

    class DocumentType(models.TextChoices):
        PURCHASE = "purchase", "Compra"
        SALE = "sale", "Venta"
        UNKNOWN = "unknown", "Desconocido"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="documents")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents"
    )
    image = models.ImageField(upload_to=_document_upload_path)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.UPLOADED)
    document_type_guess = models.CharField(
        max_length=10, choices=DocumentType.choices, default=DocumentType.UNKNOWN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CompanyScopedManager()

    class Meta:
        indexes = [
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self):
        return f"Documento #{self.pk} ({self.status})"


class DocumentExtraction(models.Model):
    document = models.OneToOneField(
        Document, on_delete=models.CASCADE, related_name="extraction"
    )
    raw_ocr_text = models.TextField(blank=True)
    # {"proveedor"/"cliente", "fecha", "items": [...], "total", ...} — ver
    # docs/DATA_MODEL.md. Datos propuestos, siempre editables antes de
    # confirmar (nunca se registran tal cual sin revisión humana).
    structured_data = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    confidence = models.CharField(max_length=10, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_extractions",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Extracción de documento #{self.document_id}"
