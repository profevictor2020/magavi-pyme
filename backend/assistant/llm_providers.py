"""Proveedores de inferencia LLM (ver docs/ARCHITECTURE.md #3.5 y
docs/DECISIONS.md ADR-003/ADR-004/ADR-010).

El Orchestrator (assistant/orchestrator.py) nunca asume un proveedor
concreto: solo conoce la interfaz `LLMProvider.completar()`. Esto es lo
que permite cambiar de modelo/runtime sin tocar el resto del sistema.
"""

from abc import ABC, abstractmethod

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class LLMProvider(ABC):
    @abstractmethod
    def completar(self, *, messages: list[dict]) -> str:
        """Envía una lista de mensajes estilo chat completion
        (`{"role": ..., "content": ...}`) y devuelve el texto crudo de
        la respuesta del modelo. No interpreta ni valida nada — eso lo
        hace el Orchestrator."""
        raise NotImplementedError


class FakeLLMProvider(LLMProvider):
    """Para tests y desarrollo del Orchestrator sin depender de GPU ni
    de un proveedor externo (ver docs/ROADMAP.md Fase 8, que ya preveía
    esto). Devuelve respuestas pre-cargadas, en orden, y registra los
    mensajes recibidos para poder verificarlos en los tests.
    """

    def __init__(self, respuestas=None):
        self._respuestas = list(respuestas or [])
        self.llamadas: list[list[dict]] = []

    def completar(self, *, messages):
        self.llamadas.append(messages)
        if not self._respuestas:
            raise AssertionError("FakeLLMProvider se quedó sin respuestas configuradas.")
        return self._respuestas.pop(0)


class OllamaLLMProvider(LLMProvider):
    """Adaptador de producción: modelo open-source autoalojado, servido
    por Ollama (API compatible con OpenAI). Ver docs/DECISIONS.md
    ADR-004 — es el proveedor por defecto, aunque su elección de modelo
    concreto se evalúa empíricamente en esta fase.
    """

    def __init__(self, *, base_url, model, timeout=60):
        self._url = f"{base_url.rstrip('/')}/v1/chat/completions"
        self._model = model
        self._timeout = timeout

    def completar(self, *, messages):
        response = requests.post(
            self._url,
            json={"model": self._model, "messages": messages, "temperature": 0},
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class DeepSeekLLMProvider(LLMProvider):
    """Adaptador para la API alojada de DeepSeek. SOLO para desarrollo y
    pruebas (ver docs/DECISIONS.md ADR-010): a diferencia de Ollama, esto
    envía el mensaje del usuario a un servidor de terceros, lo que
    contradice el requisito de IA privada para producción. Nunca es el
    `LLM_PROVIDER` por defecto; se activa explícitamente.
    """

    URL = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self, *, api_key, model="deepseek-chat", timeout=30):
        if not api_key:
            raise ImproperlyConfigured(
                "DEEPSEEK_API_KEY no configurada (requerida para LLM_PROVIDER=deepseek_dev)."
            )
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def completar(self, *, messages):
        response = requests.post(
            self.URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": messages, "temperature": 0},
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def get_llm_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER
    if provider == "fake":
        return FakeLLMProvider()
    if provider == "ollama":
        return OllamaLLMProvider(
            base_url=settings.LLM_OLLAMA_BASE_URL, model=settings.LLM_OLLAMA_MODEL
        )
    if provider == "deepseek_dev":
        return DeepSeekLLMProvider(
            api_key=settings.DEEPSEEK_API_KEY, model=settings.DEEPSEEK_MODEL
        )
    raise ImproperlyConfigured(f"LLM_PROVIDER desconocido: {provider!r}")
