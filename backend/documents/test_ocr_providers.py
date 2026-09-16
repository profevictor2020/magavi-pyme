import tempfile

from django.test import TestCase
from PIL import Image, ImageDraw, ImageFont

from .ocr_providers import FakeOCRProvider, TesseractOCRProvider

# Fuente grande y en negrita: con la fuente bitmap por defecto de Pillow,
# Tesseract confunde dígitos parecidos (3/8) en textos chicos. Esto no es
# un bug del proveedor, es una limitación real de OCR sobre texto poco
# nítido — se usa una fuente más clara para que el test sea estable.
_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


class TesseractOCRProviderTests(TestCase):
    """Prueba OCR real (Tesseract, ver docs/DECISIONS.md ADR-011), no un
    mock: genera una imagen sintética con texto conocido y verifica que
    se reconoce razonablemente.
    """

    def test_extracts_text_from_a_synthetic_image(self):
        image = Image.new("RGB", (600, 120), color="white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(_FONT_PATH, 36)
        draw.text((10, 30), "FACTURA TOTAL 12345", fill="black", font=font)

        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            image.save(tmp.name)

            provider = TesseractOCRProvider(lang="eng")
            texto = provider.extraer_texto(tmp.name)

        self.assertIn("FACTURA", texto.upper())
        self.assertIn("12345", texto)


class FakeOCRProviderTests(TestCase):
    def test_returns_configured_text(self):
        provider = FakeOCRProvider("texto de prueba")
        self.assertEqual(provider.extraer_texto("ruta/no/importa.png"), "texto de prueba")
