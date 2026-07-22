"""The Meridian National Customer Service Concierge graph.

A custom LangGraph StateGraph implementing the classic agent loop:

    START -> agent -> (tools? -> agent)* -> END

Exported as `graph` for LangSmith / LangGraph CLI deployment.
"""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from concierge.context import get_prompt
from concierge.state import ConciergeState
from concierge.tools import TOOLS

load_dotenv(override=True)

_CUSTOMER_ID_RE = re.compile(r"CUST-\d{4}")
_CUSTOMER_ID_TOOLS = {"account_lookup", "recent_transactions"}

# The system prompt (AGENTS.md) is pulled from LangSmith Context Hub at module
# import; a hub edit is picked up on the next process start. Falls back to the
# seed in concierge.prompts.SYSTEM_PROMPT when the hub is unreachable.
SYSTEM_PROMPT = get_prompt()


def _make_model() -> ChatOpenAI:
    model_name = os.getenv("CONCIERGE_MODEL", "gpt-4o-mini")
    base_url = os.getenv("BASE_URL")
    if base_url:
        # Route through the LangSmith LLM Gateway: callers authenticate with
        # their LangSmith API key; provider keys live in Provider Secrets.
        client = ChatOpenAI(
            model=model_name,
            temperature=0.2,
            base_url=base_url,
            api_key=os.environ["LANGSMITH_API_KEY"],
        )
    else:
        client = ChatOpenAI(model=model_name, temperature=0.2)
    return client.bind_tools(TOOLS)


def _guard_masked_customer_id(state: ConciergeState, tool_calls: list) -> None:
    """Fail loud if a real CUST-#### id was upstream-masked before a tool call.

    When the LLM Gateway PII policy over-matches a valid ``CUST-####`` id it
    rewrites it into a placeholder token before it reaches tool arguments, so
    the lookup returns empty and the rep is told the id is invalid. Detecting
    the mismatch here surfaces the redaction rather than proceeding silently.
    """
    if not os.getenv("BASE_URL"):
        return
    user_has_customer_id = any(
        isinstance(m, HumanMessage)
        and isinstance(m.content, str)
        and _CUSTOMER_ID_RE.search(m.content)
        for m in state["messages"]
    )
    if not user_has_customer_id:
        return
    for call in tool_calls:
        if call.get("name") not in _CUSTOMER_ID_TOOLS:
            continue
        customer_id = (call.get("args") or {}).get("customer_id")
        if isinstance(customer_id, str) and not _CUSTOMER_ID_RE.fullmatch(customer_id):
            raise ValueError(
                "Customer id was masked upstream (likely by the LLM Gateway PII "
                f"redaction policy): user referenced a CUST-#### id but the "
                f"{call.get('name')} tool call received customer_id="
                f"{customer_id!r}. Refusing to query with a masked id."
            )


def agent_node(state: ConciergeState) -> dict:
    """Call the LLM with the message history plus the system prompt."""
    model = _make_model()
    messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    response = model.invoke(messages)

    retrieval_calls = state.get("retrieval_calls", 0)
    tool_calls = getattr(response, "tool_calls", None) or []
    _guard_masked_customer_id(state, tool_calls)
    new_retrievals = sum(
        1 for call in tool_calls if call.get("name") == "search_banking_docs"
    )

    return {
        "messages": [response],
        "retrieval_calls": retrieval_calls + new_retrievals,
    }


def _build_graph():
    builder = StateGraph(ConciergeState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        tools_condition,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "agent")
    return builder.compile()


graph = _build_graph()
