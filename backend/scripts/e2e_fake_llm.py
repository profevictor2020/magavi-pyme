"""Servidor HTTP determinístico que imita la API compatible con OpenAI de
Ollama, usado SOLO por el job de CI `e2e` (ver docker-compose.e2e.yml y
docs/ROADMAP.md Fase 12) para correr el guion de demo completo contra un
LLM real predecible, sin red externa ni GPU.

No es un mock de un test unitario (esos usan FakeLLMProvider en Python,
ver assistant/llm_providers.py): este es un servicio HTTP real que habla
el mismo protocolo que Ollama, para probar el cliente HTTP real
(OllamaLLMProvider) de punta a punta con Playwright, tal como se validó
a mano en las Fases 8/9/10.

Distingue dos prompts de sistema distintos (el del asistente
conversacional vs. el de estructuración de documentos, ver
assistant/orchestrator.py y documents/structuring.py) y resuelve
`product_id` leyendo el catálogo que el propio backend incluye en el
prompt — nunca asume ids fijos, porque en un run de principio a fin no
son predecibles (dependen de qué se creó antes en la base de datos).
"""

import json
import re
import unicodedata
from http.server import BaseHTTPRequestHandler, HTTPServer

DOCUMENT_PROMPT_MARKER = "boletas y facturas chilenas"


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize(text: str) -> str:
    return _strip_accents(text or "").lower()


def _extraer_catalogo(system_text: str) -> list[tuple[int, str]]:
    # El nombre corta antes de "(stock actual: ...)" — ver
    # assistant/orchestrator.py::_construir_contexto_catalogo, que ahora
    # incluye el stock real de cada producto en esa misma línea.
    return [
        (int(product_id), name.strip())
        for product_id, name in re.findall(r"product_id=(\d+): ([^\n(]+)", system_text)
    ]


def _buscar_producto(catalogo, texto):
    texto_norm = _normalize(texto)
    for product_id, name in catalogo:
        if _normalize(name) in texto_norm:
            return product_id
    return catalogo[0][0] if catalogo else None


def _primer_numero(texto: str):
    match = re.search(r"(\d+(?:[.,]\d+)?)", texto)
    return match.group(1).replace(",", ".") if match else None


def _responder_intent_asistente(mensaje: str, catalogo) -> dict:
    texto = _normalize(mensaje)

    if "cuanto" in texto and "vend" in texto:
        return {"intent": "consultar_ventas", "parameters": {}}

    if "stock" in texto and ("bajo" in texto or "queda" in texto):
        return {"intent": "consultar_stock_bajo", "parameters": {}}

    if "vend" in texto:
        product_id = _buscar_producto(catalogo, mensaje)
        cantidad = _primer_numero(texto)
        precio_match = re.search(r"a\s*\$?\s*(\d+(?:[.,]\d+)?)", texto)
        return {
            "intent": "crear_venta",
            "parameters": {
                "items": [
                    {
                        "product_id": product_id,
                        "quantity": cantidad or "1",
                        "unit_price": (precio_match.group(1) if precio_match else None),
                    }
                ],
                "customer_name": "",
            },
        }

    if "compr" in texto:
        product_id = _buscar_producto(catalogo, mensaje)
        cantidad = _primer_numero(texto)
        return {
            "intent": "registrar_compra",
            "parameters": {
                "items": [{"product_id": product_id, "quantity": cantidad or "1"}],
                "supplier_name": "",
            },
        }

    return {"intent": "no_entendido", "parameters": {"motivo": "mensaje de prueba no reconocido"}}


def _responder_estructuracion_documento(raw_text: str, catalogo) -> dict:
    product_id = _buscar_producto(catalogo, raw_text)
    cantidad = _primer_numero(raw_text) or "1"
    return {
        "document_type": "purchase",
        "counterparty_name": "Distribuidora ABC",
        "date": None,
        "items": [
            {
                "product_id": product_id,
                "product_name_raw": "Cafe",
                "quantity": cantidad,
                "unit_price": "1500",
            }
        ],
        "total": None,
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        data = json.loads(body) if body else {}
        messages = data.get("messages", [])

        system_text = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
        user_messages = [m.get("content", "") for m in messages if m.get("role") == "user"]
        catalogo = _extraer_catalogo(system_text)

        ultimo_mensaje = user_messages[-1] if user_messages else ""
        if DOCUMENT_PROMPT_MARKER in system_text:
            respuesta = _responder_estructuracion_documento(ultimo_mensaje, catalogo)
        else:
            respuesta = _responder_intent_asistente(ultimo_mensaje, catalogo)

        payload = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": json.dumps(respuesta)}}]}
        ).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 11434), Handler).serve_forever()
