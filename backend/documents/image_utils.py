import io

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image

MAX_DIMENSION_PX = 6000


def strip_exif(uploaded_file):
    """Vuelve a codificar la imagen sin metadatos EXIF (puede incluir
    geolocalización — ver docs/SECURITY.md #6) antes de guardarla.
    Pillow no conserva EXIF al guardar salvo que se pase explícitamente.
    """
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    image.load()

    save_format = image.format or "JPEG"
    if image.mode in ("RGBA", "P") and save_format == "JPEG":
        image = image.convert("RGB")

    buffer = io.BytesIO()
    image.save(buffer, format=save_format)
    buffer.seek(0)

    return InMemoryUploadedFile(
        buffer,
        field_name="image",
        name=uploaded_file.name,
        content_type=uploaded_file.content_type,
        size=buffer.getbuffer().nbytes,
        charset=None,
    )
