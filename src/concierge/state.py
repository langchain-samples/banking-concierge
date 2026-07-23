"""Graph state schema for the concierge agent."""

from __future__ import annotations

from typing import Optional

from typing_extensions import NotRequired

from langgraph.graph import MessagesState


class ConciergeState(MessagesState):
    """Messages plus a small counter for tracing observability.

    `retrieval_calls` increments each time the agent calls search_banking_docs.
    A high value on a single trace is a useful signal for Engine to cluster
    on as a "agent looped on retrieval" anomaly.

    `conversation_id` and `rep_id` carry the thread and rep identity through to
    the root run's LangSmith metadata (thread grouping and per-rep attribution).
    """

    retrieval_calls: int
    conversation_id: NotRequired[Optional[str]]
    rep_id: NotRequired[Optional[str]]
