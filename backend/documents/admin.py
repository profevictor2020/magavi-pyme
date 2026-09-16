from django.contrib import admin

from .models import Document, DocumentExtraction


class DocumentExtractionInline(admin.StackedInline):
    model = DocumentExtraction
    extra = 0


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "status", "document_type_guess", "created_at"]
    list_filter = ["status", "document_type_guess"]
    inlines = [DocumentExtractionInline]
