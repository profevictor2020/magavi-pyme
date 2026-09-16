from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .image_test_helpers import make_test_image
from .serializers import DocumentUploadSerializer


class DocumentImageValidationTests(TestCase):
    """Ver docs/SECURITY.md #6: whitelist de tipo, tamaño máximo,
    verificación real de que el archivo es una imagen válida.
    """

    def test_accepts_a_valid_png(self):
        serializer = DocumentUploadSerializer(data={"image": make_test_image()})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_disallowed_content_type(self):
        bad_file = SimpleUploadedFile(
            "archivo.txt", b"no soy una imagen", content_type="text/plain"
        )

        serializer = DocumentUploadSerializer(data={"image": bad_file})

        self.assertFalse(serializer.is_valid())
        self.assertIn("image", serializer.errors)

    def test_rejects_file_that_is_not_really_an_image(self):
        fake_image = SimpleUploadedFile(
            "malicioso.png", b"esto no es un png de verdad", content_type="image/png"
        )

        serializer = DocumentUploadSerializer(data={"image": fake_image})

        self.assertFalse(serializer.is_valid())

    @override_settings(DOCUMENT_MAX_UPLOAD_SIZE_BYTES=100)
    def test_rejects_file_larger_than_max_size(self):
        serializer = DocumentUploadSerializer(data={"image": make_test_image(size=(800, 800))})

        self.assertFalse(serializer.is_valid())
        self.assertIn("image", serializer.errors)

    def test_rejects_image_larger_than_max_dimensions(self):
        from . import serializers as serializers_module

        original = serializers_module.MAX_DIMENSION_PX
        serializers_module.MAX_DIMENSION_PX = 50
        try:
            serializer = DocumentUploadSerializer(data={"image": make_test_image(size=(200, 200))})
            self.assertFalse(serializer.is_valid())
        finally:
            serializers_module.MAX_DIMENSION_PX = original
