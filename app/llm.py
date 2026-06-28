import os
from collections.abc import AsyncIterator, Iterator

from langchain_core.runnables import Runnable
from langchain_ollama import OllamaLLM

_FAKE_OUTPUT = (
    "• Résumé factice (mode hors-ligne, aucune requête envoyée à Ollama).\n"
    "• Définis TLDW_LLM_BACKEND=ollama pour utiliser le vrai modèle.\n"
    "• Ceci est un placeholder déterministe.\n"
)


class FakeLLM(Runnable):
    """Deterministic offline stand-in for OllamaLLM. Streams a canned summary."""

    def invoke(self, input, config=None, **kwargs) -> str:
        return _FAKE_OUTPUT

    def stream(self, input, config=None, **kwargs) -> Iterator[str]:
        for word in _FAKE_OUTPUT.split(" "):
            yield word + " "

    async def astream(self, input, config=None, **kwargs) -> AsyncIterator[str]:
        for word in _FAKE_OUTPUT.split(" "):
            yield word + " "


def get_llm() -> Runnable:
    """Return the configured LLM backend.

    TLDW_LLM_BACKEND=fake  → deterministic FakeLLM (no Ollama required)
    TLDW_LLM_BACKEND=ollama (default) → OllamaLLM via OLLAMA_MODEL
    """
    if os.getenv("TLDW_LLM_BACKEND", "ollama") == "fake":
        return FakeLLM()
    return OllamaLLM(
        model=os.getenv("OLLAMA_MODEL", "gemma4"),
        temperature=0.3,
        reasoning=False,
    )
