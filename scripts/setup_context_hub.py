"""One-shot Context Hub setup for the banking-concierge demo.

Seeds the LangSmith Context Hub with:
  1. The agent's ``AGENTS.md`` (the buggy, hallucination-prone system prompt) —
     the runtime source of truth that ``concierge.context.get_prompt()`` pulls.
     The setup promotes the initial prompt commit to the ``production`` tag.
  2. A small library of show-only ``SKILL.md`` repos to demonstrate the hub's
     breadth (the agent does not load these at runtime).

Run once after configuring ``.env``:

    uv run python -m scripts.setup_context_hub

Requires ``LANGSMITH_API_KEY`` (and ``LANGSMITH_WORKSPACE_ID`` when the key's
default workspace differs from the demo workspace).
"""

from dotenv import load_dotenv

load_dotenv(override=True)

import os
import sys

from concierge.context import CONTEXT_HUB_REPO
from concierge.context_hub import push_agents_md, push_demo_skills


def main() -> None:
    if not os.getenv("LANGSMITH_API_KEY"):
        print("Error: LANGSMITH_API_KEY not set.")
        sys.exit(1)

    push_agents_md()
    push_demo_skills()

    print("\nContext Hub setup complete.")
    print(f"  Agent repo: {CONTEXT_HUB_REPO} (AGENTS.md)")
    print("  The agent now pulls its system prompt from the hub at runtime.")
    print("  Edit AGENTS.md in the Context Hub UI to fix the hallucination bug.")


if __name__ == "__main__":
    main()
