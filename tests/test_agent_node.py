"""Tests that agent_node only sends redacted human turns to the model."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ["LANGSMITH_TRACING"] = "false"

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langsmith import run_trees  # noqa: E402

from concierge.redaction import trace_anonymizer  # noqa: E402

graph_module = importlib.import_module("concierge.graph")

SSN = "552-19-4488"
PAN = "4242 4242 4242 4242"
PASTED = f"SSN {SSN}, Visa {PAN} exp 08/29 CVV 314. Pull up their account."


class _FakeModel:
    def __init__(self) -> None:
        self.received: list = []

    def invoke(self, messages):
        self.received = messages
        return AIMessage(content="Need the CUST-#### ID.")


def test_agent_node_sends_redacted_copies_and_stores_mapping(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(graph_module, "_make_model", lambda: fake)
    human = HumanMessage(content=PASTED)
    state = {"messages": [human], "retrieval_calls": 0}

    result = graph_module.agent_node(state)

    sent = " ".join(str(m.content) for m in fake.received)
    for raw in (SSN, PAN, "08/29", "314"):
        assert raw not in sent
    assert "[SSN_1]" in sent and "[CARD_1]" in sent and "[CVV_1]" in sent
    assert human.content == PASTED
    assert state["messages"][0] is human
    assert result["pii_map"] == {
        "[SSN_1]": SSN,
        "[CARD_1]": PAN,
        "[EXP_1]": "08/29",
        "[CVV_1]": "314",
    }


def test_agent_node_reuses_existing_mapping(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(graph_module, "_make_model", lambda: fake)
    state = {
        "messages": [HumanMessage(content=f"Same SSN {SSN}")],
        "pii_map": {"[SSN_1]": SSN},
    }

    result = graph_module.agent_node(state)

    assert fake.received[-1].content == "Same SSN [SSN_1]"
    assert result["pii_map"] == {"[SSN_1]": SSN}


def test_tracing_client_uses_anonymizer():
    client = run_trees.get_cached_client()
    assert client._anonymizer is trace_anonymizer
    masked = client._hide_run_inputs({"messages": [{"content": PASTED}]})
    assert SSN not in repr(masked) and PAN not in repr(masked)
