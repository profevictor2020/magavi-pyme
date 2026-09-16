import json


def parse_json_object(texto: str):
    """Parsea un texto como un objeto JSON, tolerando el caso común de un
    LLM que envuelve su respuesta en un bloque de código ```json pese a
    la instrucción de no hacerlo. Devuelve None si no es un objeto JSON
    válido (nunca lanza), para que el llamador decida cómo reaccionar
    (reintentar, pedir aclaración, etc.).
    """
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`").strip()
        if texto.lower().startswith("json"):
            texto = texto[4:].strip()
    try:
        data = json.loads(texto)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None
