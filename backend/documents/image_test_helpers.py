import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageDraw


def make_test_image(
    text="FACTURA\nTOTAL 1000",
    size=(400, 200),
    content_type="image/png",
    filename="documento.png",
):
    """Genera una imagen sintética en memoria con texto dibujado, para no
    necesitar fixtures binarios en el repo. Sirve tanto para probar OCR
    real (Tesseract puede leer el texto dibujado) como para las pruebas
    de la API que solo necesitan un archivo de imagen válido.
    """
    image = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(image)
    draw.multiline_text((10, 10), text, fill="black")

    buffer = io.BytesIO()
    image_format = "PNG" if content_type == "image/png" else "JPEG"
    image.save(buffer, format=image_format)
    buffer.seek(0)

    return SimpleUploadedFile(filename, buffer.read(), content_type=content_type)
