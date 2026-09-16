"""Proveedores de OCR (ver docs/ARCHITECTURE.md #3.6, docs/DECISIONS.md
ADR-005 y ADR-011). Mismo patrón que `assistant/llm_providers.py`: una
interfaz mínima para que el resto del sistema nunca dependa de un motor
concreto.
"""

from abc import ABC, abstractmethod

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class OCRProvider(ABC):
    @abstractmethod
    def extraer_texto(self, image_path: str) -> str:
        """Devuelve el texto crudo detectado en la imagen. No interpreta
        ni estructura nada — eso lo hace documents/structuring.py."""
        raise NotImplementedError


class FakeOCRProvider(OCRProvider):
    """Para tests: devuelve un texto fijo sin tocar disco ni CPU."""

    def __init__(self, texto="FACTURA\nProveedor: Distribuidora ABC\nTotal: 10000"):
        self._texto = texto

    def extraer_texto(self, image_path: str) -> str:
        return self._texto


class TesseractOCRProvider(OCRProvider):
    """Adaptador real y self-hosted (ver docs/DECISIONS.md ADR-011):
    Tesseract vía `pytesseract`, instalable con un paquete del sistema
    operativo (`apt install tesseract-ocr`), sin GPU y sin descargar
    modelos pesados — a diferencia de PaddleOCR/docTR (ADR-005), que
    siguen siendo la opción a evaluar si la calidad de Tesseract resulta
    insuficiente en boletas/facturas chilenas reales.
    """

    def __init__(self, *, lang=None):
        self._lang = lang or settings.OCR_TESSERACT_LANG

    def extraer_texto(self, image_path: str) -> str:
        import pytesseract
        from PIL import Image

        with Image.open(image_path) as img:
            return pytesseract.image_to_string(img, lang=self._lang)


def get_ocr_provider() -> OCRProvider:
    provider = settings.OCR_PROVIDER
    if provider == "fake":
        return FakeOCRProvider()
    if provider == "tesseract":
        return TesseractOCRProvider()
    raise ImproperlyConfigured(f"OCR_PROVIDER desconocido: {provider!r}")
