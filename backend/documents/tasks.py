from celery import shared_task

from .models import Document, DocumentExtraction
from .ocr_providers import get_ocr_provider
from .structuring import estructurar_documento


@shared_task
def procesar_documento(document_id):
    """Pipeline async: OCR -> estructuración vía LLM -> DocumentExtraction
    (ver docs/ROADMAP.md Fase 9, docs/DECISIONS.md ADR-007). Nunca
    registra una compra/venta por sí sola: solo deja la propuesta lista
    para revisión humana (Document pasa a needs_review).

    Se busca el documento con el manager base (sin scope de empresa):
    la tarea es interna y confiable, y `document_id` ya fue resuelto con
    scope de empresa por la vista que la encoló (ver
    docs/ARCHITECTURE.md #4 sobre CompanyScopedManager).
    """
    try:
        document = Document._base_manager.select_related("company").get(pk=document_id)
    except Document.DoesNotExist:
        return

    document.status = Document.Status.PROCESSING
    document.save(update_fields=["status", "updated_at"])

    try:
        ocr_provider = get_ocr_provider()
        raw_text = ocr_provider.extraer_texto(document.image.path)

        structured = estructurar_documento(company=document.company, raw_text=raw_text)

        DocumentExtraction.objects.update_or_create(
            document=document,
            defaults={"raw_ocr_text": raw_text, "structured_data": structured},
        )

        valid_types = dict(Document.DocumentType.choices)
        document.document_type_guess = (
            structured.get("document_type")
            if structured.get("document_type") in valid_types
            else Document.DocumentType.UNKNOWN
        )
        document.status = Document.Status.NEEDS_REVIEW
        document.save(update_fields=["status", "document_type_guess", "updated_at"])
    except Exception:
        document.status = Document.Status.FAILED
        document.save(update_fields=["status", "updated_at"])
        raise
