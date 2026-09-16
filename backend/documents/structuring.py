"""Estructuración de documentos capturados por foto (ver
docs/ARCHITECTURE.md #3.6, docs/ROADMAP.md Fase 9).

Reutiliza el mismo LLMProvider del asistente (Fase 8) para convertir el
texto crudo de OCR en datos propuestos — nunca se registra nada
automáticamente: el usuario siempre revisa y confirma antes de que se
cree una compra/venta real (ver docs/SECURITY.md #7).
"""

from assistant.llm_providers import get_llm_provider
from catalog.models import Product
from core.json_utils import parse_json_object

SYSTEM_PROMPT = """Eres un asistente que extrae datos estructurados de \
boletas y facturas chilenas a partir de texto obtenido por OCR (puede \
tener errores de reconocimiento). Responde EXCLUSIVAMENTE con un JSON \
de esta forma:

{"document_type": "purchase" o "sale" o "unknown",
 "counterparty_name": "<proveedor o cliente, o null>",
 "date": "<fecha YYYY-MM-DD si se puede inferir, o null>",
 "items": [{"product_id": <int o null>, "product_name_raw": "<texto tal cual>", \
"quantity": "<numero>", "unit_price": "<numero o null>"}],
 "total": "<numero o null>"}

Usa product_id solo si el nombre del ítem coincide claramente con un \
producto del catálogo entregado a continuación; si no hay una \
coincidencia clara, deja product_id en null (nunca inventes un id). \
Nunca respondas con texto fuera del JSON."""

_DEFAULT_ESTRUCTURA = {
    "document_type": "unknown",
    "counterparty_name": None,
    "date": None,
    "items": [],
    "total": None,
}


def _construir_contexto_catalogo(company) -> str:
    productos = list(
        Product.objects.for_company(company).filter(is_active=True).order_by("name")[:200]
    )
    if not productos:
        return "Catálogo de la empresa: (sin productos registrados todavía)."
    lineas = [f"- product_id={p.id}: {p.name}" for p in productos]
    return "Catálogo de la empresa (product_id: nombre):\n" + "\n".join(lineas)


def estructurar_documento(*, company, raw_text, llm_provider=None) -> dict:
    """Devuelve una propuesta de estructuración (dict); nunca ejecuta
    nada. Si el LLM no devuelve un JSON válido, devuelve una estructura
    vacía para que el usuario la complete a mano en la revisión.
    """
    llm_provider = llm_provider or get_llm_provider()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": _construir_contexto_catalogo(company)},
        {"role": "user", "content": raw_text or "(sin texto detectado)"},
    ]

    respuesta = llm_provider.completar(messages=messages)
    parsed = parse_json_object(respuesta)

    if parsed is None:
        return dict(_DEFAULT_ESTRUCTURA)

    resultado = dict(_DEFAULT_ESTRUCTURA)
    resultado.update(parsed)
    if not isinstance(resultado.get("items"), list):
        resultado["items"] = []
    return resultado
