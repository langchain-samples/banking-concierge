"""Regression tests for the banking documentation retrieval path."""

from __future__ import annotations

import pytest

from concierge import retrieval, tools

GATEWAY_BASE_URL = "https://gateway.smith.langchain.com/openai/v1"


@pytest.fixture(autouse=True)
def _gateway_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_URL", GATEWAY_BASE_URL)
    monkeypatch.setenv("OPENAI_BASE_URL", GATEWAY_BASE_URL)
    monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2-must-not-be-used")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key")


def test_embeddings_bypass_the_langsmith_gateway() -> None:
    embeddings = retrieval._make_embeddings()

    assert embeddings.openai_api_base == "https://api.openai.com/v1"
    assert "gateway.smith.langchain.com" not in (embeddings.openai_api_base or "")


def test_embeddings_do_not_use_the_langsmith_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    embeddings = retrieval._make_embeddings()

    assert embeddings.openai_api_key is not None
    assert embeddings.openai_api_key.get_secret_value() == "sk-test-openai-key"


def test_search_reports_retrieval_outage_distinctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(query: str, k: int = 4) -> list:
        raise RuntimeError("Deployment 'text-embedding-3-small' not found")

    monkeypatch.setattr(tools, "retrieve", _boom)

    result = tools.search_banking_docs.invoke({"query": "wire cutoff"})

    assert result.startswith("RETRIEVAL_UNAVAILABLE:")
    assert "No relevant documentation found." not in result


def test_search_reports_zero_hits_distinctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tools, "retrieve", lambda query, k=4: [])

    result = tools.search_banking_docs.invoke({"query": "wire cutoff"})

    assert result == "No relevant documentation found."
