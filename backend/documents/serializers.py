from decimal import Decimal

from django.conf import settings
from PIL import Image
from rest_framework import serializers

from .image_utils import MAX_DIMENSION_PX
from .models import Document, DocumentExtraction


class DocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "image", "status", "document_type_guess", "created_at"]
        read_only_fields = ["id", "status", "document_type_guess", "created_at"]

    def validate_image(self, file):
        if file.size > settings.DOCUMENT_MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.DOCUMENT_MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            raise serializers.ValidationError(
                f"El archivo supera el tamaño máximo permitido ({max_mb} MB)."
            )

        content_type = getattr(file, "content_type", None)
        if content_type not in settings.DOCUMENT_ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(f"Tipo de archivo no permitido: {content_type!r}.")

        try:
            image = Image.open(file)
            image.verify()
        except Exception as exc:
            raise serializers.ValidationError("El archivo no es una imagen válida.") from exc

        file.seek(0)
        # verify() deja la imagen inutilizable para más operaciones; se
        # reabre para chequear dimensiones.
        image = Image.open(file)
        if image.width > MAX_DIMENSION_PX or image.height > MAX_DIMENSION_PX:
            raise serializers.ValidationError(
                f"La imagen es demasiado grande (máximo {MAX_DIMENSION_PX}x{MAX_DIMENSION_PX}px)."
            )
        file.seek(0)
        return file


class DocumentExtractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentExtraction
        fields = [
            "raw_ocr_text",
            "structured_data",
            "confidence",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = fields


class DocumentSerializer(serializers.ModelSerializer):
    extraction = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "image",
            "status",
            "document_type_guess",
            "created_at",
            "updated_at",
            "extraction",
        ]
        read_only_fields = fields

    def get_extraction(self, obj):
        extraction = getattr(obj, "extraction", None)
        if extraction is None:
            return None
        return DocumentExtractionSerializer(extraction).data


class DocumentConfirmItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    unit_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal("0")
    )


class DocumentConfirmSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=["purchase", "sale"])
    party_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    items = DocumentConfirmItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Debe haber al menos un ítem.")
        return value
