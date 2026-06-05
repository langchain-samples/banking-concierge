"""LangSmith Context Hub setup-time helpers for the banking-concierge demo.

``push_agents_md()`` is called once by ``scripts/setup_context_hub.py`` to seed
Context Hub with the initial ``AGENTS.md`` (the buggy, hallucination-prone
system prompt from ``concierge.prompts.SYSTEM_PROMPT``) and promote that commit
to the ``production`` environment tag. The runtime pulls ``:production`` (see
``concierge.context.get_prompt``), so this gives the demo a hub-driven baseline;
after that, ``AGENTS.md`` is edited and re-promoted in the Context Hub UI.

``push_demo_skills()`` seeds a handful of standalone Skill repos that demonstrate
the breadth of Context Hub. The agent does NOT load these at runtime — they exist
purely so a presenter can show what a skills library looks like in the hub.

The two raw-REST calls below exist only because the Python SDK doesn't yet expose
``source`` on push_agent/push_skill or a workspace-handle setter. When the SDK
catches up, this file collapses to a few one-line SDK calls.
"""

from __future__ import annotations

import os

import requests
from langsmith import Client
from langsmith.schemas import FileEntry

from concierge.context import CONTEXT_HUB_REPO
from concierge.prompts import SYSTEM_PROMPT

_API = "https://api.smith.langchain.com/api/v1"


def _rest_headers() -> dict:
    headers = {
        "x-api-key": os.getenv("LANGSMITH_API_KEY"),
        "Content-Type": "application/json",
    }
    if ws := os.getenv("LANGSMITH_WORKSPACE_ID", "").strip():
        headers["X-Tenant-Id"] = ws
    return headers


def _promote_to_production(client: Client) -> None:
    """Tag the agent repo's latest commit as the ``production`` environment.

    The runtime pulls ``:production`` (see ``concierge.context.get_prompt``), so
    promotion is what makes a Context Hub commit live. Owner ``-`` resolves to
    the current workspace. Best-effort: a failure here doesn't undo the seed.
    """
    try:
        agent = client.pull_agent(CONTEXT_HUB_REPO)
        client._create_commit_tags(f"-/{CONTEXT_HUB_REPO}", str(agent.commit_id), "production")
        print(f"  Promoted commit {agent.commit_hash[:8]} to 'production'.")
    except Exception as exc:  # noqa: BLE001
        print(
            f"  WARNING: could not promote to 'production' ({exc}).\n"
            "  Promote the latest commit to Production in the Context Hub UI, "
            "or the runtime falls back to the local seed prompt."
        )


def push_agents_md() -> None:
    """Seed Context Hub with the initial AGENTS.md.

    Called by ``scripts/setup_context_hub.py``. Does three things the Python SDK
    can't:
      1. Sets a workspace tenant_handle if missing (the UI listing filter hides
         repos with owner=null).
      2. Creates the repo with source="internal" (the marker the UI listing
         filters on; the SDK's push_agent doesn't expose it).
      3. Commits the seed content via the SDK.
    """
    print(f"\n[*] Seeding Context Hub repo '{CONTEXT_HUB_REPO}' with initial AGENTS.md...")

    headers = _rest_headers()

    # 1. tenant_handle (only if not already set)
    settings = requests.get(f"{_API}/settings", headers=headers).json()
    if not settings.get("tenant_handle"):
        handle = "banking-concierge"
        requests.post(f"{_API}/settings/handle", headers=headers, json={"tenant_handle": handle})
        print(f"  Set workspace tenant_handle to '{handle}'.")

    # 2. Repo with source=internal (idempotent — 409 if it already exists, which is fine)
    requests.post(
        f"{_API}/repos/",
        headers=headers,
        json={
            "repo_handle": CONTEXT_HUB_REPO,
            "repo_type": "agent",
            "source": "internal",
            "is_public": False,
            "description": "Meridian National concierge agent instructions (buggy, for Engine demo)",
        },
    )

    # 3. Commit the seed (idempotent — if the file already exists, this is a no-op commit)
    client = Client()
    client.push_agent(CONTEXT_HUB_REPO, files={"AGENTS.md": FileEntry(content=SYSTEM_PROMPT)})
    print(f"  Pushed {len(SYSTEM_PROMPT)} chars.")

    # 4. Promote the seed commit to the `production` environment so the runtime,
    #    which pulls `:production`, uses it as the hub-driven baseline.
    _promote_to_production(client)


# ── Demo-only Skills ──────────────────────────────────────────────────────────
# Standalone skills the agent does NOT load. They exist so the Context Hub view
# has something to point at when explaining the breadth of what teams manage in
# the hub. Each is a small SKILL.md the presenter can open and talk through.

_DEMO_SKILLS = {
    "banking-concierge-dispute-intake-skill": """# banking-concierge-dispute-intake-skill

## Purpose

Walk a customer service rep through filing a card transaction dispute so the
case lands in the back office with everything the dispute team needs.

## When to use

- Account holder reports an unauthorized or incorrect card charge
- Rep needs to open a chargeback before the network deadline
- A merchant refund hasn't posted within the expected window

## Inputs

- `customer_id` (str): Meridian National customer identifier
- `transaction_id` (str): the disputed transaction
- `reason` (str): "unauthorized", "duplicate", "wrong_amount", "not_received"

## Output

A structured dispute record: `{case_id, customer_id, transaction_id, reason,
provisional_credit_eligible, network_deadline}` plus the disclosure script the
rep should read to the customer.
""",
    "banking-concierge-wire-cutoff-lookup-skill": """# banking-concierge-wire-cutoff-lookup-skill

## Purpose

Return the same-day cutoff time for a wire transfer so the rep can tell the
customer whether their wire makes today's settlement window.

## When to use

- Customer asks "will my wire go out today?"
- Rep is initiating a domestic or international wire near end of day
- Confirming cutoffs around bank holidays

## Inputs

- `wire_type` (str): "domestic" or "international"
- `currency` (str): ISO 4217 code (international only)
- `as_of` (ISO datetime): the rep's local time

## Output

`{cutoff_local, settles_today, next_business_day}` — always sourced from the
published cutoff schedule, never estimated from memory.
""",
    "banking-concierge-kyc-verification-skill": """# banking-concierge-kyc-verification-skill

## Purpose

Guide the rep through Know-Your-Customer identity verification on a live call
without reading sensitive fields aloud.

## When to use

- Inbound caller must be verified before account changes
- Step-up verification on a high-risk request (wire, address change)
- Re-verification after a fraud flag

## Verification axes

- **Knowledge**: last 4 of SSN, date of birth, recent transaction amount
- **Possession**: one-time passcode to the phone/email on file
- **Risk**: escalate to a supervisor below a confidence threshold

## Output

`{verified, method, confidence, escalate}` — the skill never echoes full SSN,
card numbers, or CVV; it confirms matches only.
""",
}


def push_demo_skills() -> None:
    """Seed a handful of standalone Skill repos in Context Hub.

    These are NOT loaded by the agent at runtime. They exist so a presenter can
    show that Context Hub holds more than just the agent's AGENTS.md — teams
    typically version a library of skills alongside their agents.
    """
    print("\n[*] Seeding demo skills in Context Hub...")

    headers = _rest_headers()
    client = Client()
    for skill_name, skill_content in _DEMO_SKILLS.items():
        # Create the repo with source=internal so it shows in the Context Hub UI
        requests.post(
            f"{_API}/repos/",
            headers=headers,
            json={
                "repo_handle": skill_name,
                "repo_type": "skill",
                "source": "internal",
                "is_public": False,
                "description": (
                    "Banking Concierge demo skill — "
                    f"{skill_name.removeprefix('banking-concierge-').removesuffix('-skill').replace('-', ' ').title()}"
                ),
            },
        )
        # Commit the SKILL.md
        client.push_skill(skill_name, files={"SKILL.md": FileEntry(content=skill_content)})
        print(f"  ✓ {skill_name}")
