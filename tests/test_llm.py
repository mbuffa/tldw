"""
Tests for app/llm.py — the env-selected LLM factory.

Note: stub_llm patches app.summarizer.get_llm, NOT app.llm.get_llm, so these
tests import directly from app.llm and see the real factory unmasked.
"""

import pytest
from langchain_ollama import OllamaLLM

from app.llm import _FAKE_OUTPUT, FakeLLM, get_llm


def test_get_llm_default_returns_ollama():
    llm = get_llm()
    assert isinstance(llm, OllamaLLM)


def test_get_llm_fake_backend(monkeypatch):
    monkeypatch.setenv("TLDW_LLM_BACKEND", "fake")
    llm = get_llm()
    assert isinstance(llm, FakeLLM)


def test_get_llm_explicit_ollama(monkeypatch):
    monkeypatch.setenv("TLDW_LLM_BACKEND", "ollama")
    llm = get_llm()
    assert isinstance(llm, OllamaLLM)


def test_fake_llm_invoke():
    result = FakeLLM().invoke("any input")
    assert result == _FAKE_OUTPUT


@pytest.mark.asyncio
async def test_fake_llm_astream_concatenates_to_full_output():
    chunks = [c async for c in FakeLLM().astream("any input")]
    assert "".join(chunks) == "".join(word + " " for word in _FAKE_OUTPUT.split(" "))


@pytest.mark.asyncio
async def test_fake_llm_works_as_chain_step():
    """FakeLLM composes with a PromptTemplate via the | operator."""
    from langchain_core.prompts import PromptTemplate

    prompt = PromptTemplate.from_template("Summarize: {text}")
    chain = prompt | FakeLLM()
    chunks = [c async for c in chain.astream({"text": "hello"})]
    assert len(chunks) > 0
    assert "".join(chunks).strip() != ""
