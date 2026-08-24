"""Tools available to the Meridian National customer service concierge agent.

A few tools have deliberate rough edges so LangSmith Engine has something
to cluster after the load generator runs:

- search_banking_docs has a vague description so the model occasionally
  re-queries multiple times rephrasing
- account_lookup raises on malformed customer IDs and on IDs prefixed with
  "X" (simulated downstream outage)
- recent_transactions raises if the model passes a runaway limit
- find_branch raises on non-zip inputs
"""

from __future__ import annotations

from langchain_core.tools import tool

from concierge.mock_data import (
    BRANCHES,
    CUSTOMERS,
    TRANSACTIONS,
    find_branch_by_zip,
)
from concierge.retrieval import retrieve


def _digits(value: str) -> str:
    """Return only the digit characters of ``value``."""
    return "".join(c for c in value if c.isdigit())


def _mask_phone(phone: str) -> str:
    """Return ``phone`` with everything but the last four digits masked."""
    digits = _digits(phone)
    return f"***-***-{digits[-4:]}" if len(digits) >= 4 else "***"


@tool
def search_banking_docs(query: str, k: int = 4) -> str:
    """Search Meridian National banking documentation.

    Args:
        query: A natural-language search query.
        k: Number of relevant chunks to return. Defaults to 4.
    """
    chunks = retrieve(query, k=k)
    if not chunks:
        return "No relevant documentation found."
    blocks = []
    for chunk in chunks:
        source = chunk.metadata.get("source", "unknown")
        blocks.append(f"[source: {source}]\n{chunk.page_content}")
    return "\n\n---\n\n".join(blocks)


@tool
def find_customer(
    ssn: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    card_last4: str | None = None,
    account_id: str | None = None,
) -> dict:
    """Resolve an account holder's customer ID from an identifier the representative already has.

    Supply at least one of the lookup keys below; every key supplied must
    match. Returns candidate matches whose ``customer_id`` is what you then
    pass to account_lookup or recent_transactions.

    Args:
        ssn: The account holder's Social Security number, with or without dashes.
        phone: A phone number on file, in any format.
        email: An email address on file.
        card_last4: The last four digits of a credit card on file.
        account_id: A bare account number (e.g. 1234), not a customer ID.
    """
    ssn, phone, email, card_last4, account_id = (
        value if value and value.strip() else None
        for value in (ssn, phone, email, card_last4, account_id)
    )
    criteria = {
        "ssn": ssn,
        "phone": phone,
        "email": email,
        "card_last4": card_last4,
        "account_id": account_id,
    }
    if all(value is None for value in criteria.values()):
        raise ValueError(
            "find_customer needs at least one of: "
            f"{', '.join(criteria)}."
        )

    matches = []
    for customer in CUSTOMERS.values():
        if ssn is not None and _digits(ssn) != _digits(customer["ssn"]):
            continue
        if phone is not None and _digits(phone) != _digits(customer["phone"]):
            continue
        if email is not None and email.strip().lower() != customer["email"].lower():
            continue
        if card_last4 is not None and not any(
            _digits(card["number"]).endswith(_digits(card_last4))
            for card in customer["credit_cards"]
        ):
            continue
        if account_id is not None and not any(
            account["account_id"] == account_id.strip()
            for account in customer["accounts"]
        ):
            continue
        matches.append(
            {
                "customer_id": customer["customer_id"],
                "name": customer["name"],
                "masked_phone": _mask_phone(customer["phone"]),
                "accounts": [
                    {"account_id": a["account_id"], "type": a["type"]}
                    for a in customer["accounts"]
                ],
            }
        )

    if not matches:
        return {
            "matches": [],
            "count": 0,
            "message": "No account holder matched those details.",
        }
    return {"matches": matches, "count": len(matches)}


@tool
def account_lookup(customer_id: str) -> dict:
    """Look up account information.

    Returns the customer's name and a list of their account IDs, account
    types, and balances. Use this when the user wants details about an
    account.

    Args:
        customer_id: The account holder's customer ID, which MUST be in the
            format CUST-#### (e.g. CUST-0001). This is the only accepted
            lookup key — do not pass an SSN, phone number, card number,
            account number, or name. If you only have one of those, call
            find_customer first to resolve the customer ID.
    """
    if customer_id.startswith("X"):
        raise RuntimeError(
            "Customer record service is temporarily unavailable. Try again later."
        )
    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        raise ValueError(
            f"No customer found with ID {customer_id!r}. "
            "Customer IDs are in the format CUST-####."
        )
    return dict(customer)


@tool
def recent_transactions(customer_id: str, limit: int = 5) -> list[dict]:
    """Retrieve a customer's most recent transactions.

    Args:
        customer_id: The customer ID (e.g. CUST-0001).
        limit: Optional number of transactions to return.
    """
    if limit <= 0:
        raise ValueError("limit must be positive")
    if limit > 50:
        raise ValueError(
            f"limit {limit} exceeds the maximum of 50. Pick a smaller number."
        )
    if customer_id not in CUSTOMERS:
        raise ValueError(
            f"No customer found with ID {customer_id!r}. "
            "Customer IDs are in the format CUST-####."
        )
    txs = TRANSACTIONS.get(customer_id, [])
    return [dict(t) for t in txs[:limit]]


@tool
def find_branch(zip_code: str) -> dict:
    """Find a Meridian National branch.

    Args:
        zip_code: A 5-digit U.S. ZIP code.
    """
    if not (isinstance(zip_code, str) and len(zip_code) == 5 and zip_code.isdigit()):
        raise ValueError(
            f"zip_code must be a 5-digit U.S. ZIP code. Got {zip_code!r}."
        )
    branch = find_branch_by_zip(zip_code)
    if branch is None:
        return {
            "match": False,
            "message": "No Meridian National branch found in our directory for that ZIP code.",
            "nearest_known": BRANCHES[0],
        }
    return {"match": True, **branch}


@tool
def transfer_funds(from_account: str, to_account: str, amount: float) -> dict:
    """Initiate a transfer between two Meridian National accounts owned by the same customer.

    Args:
        from_account: The source account ID.
        to_account: The destination account ID.
        amount: The dollar amount to transfer.
    """
    if amount <= 0:
        raise ValueError("amount must be positive")
    confirmation = f"MNB-XFER-{abs(hash((from_account, to_account, amount))) % 10_000_000:07d}"
    return {
        "status": "submitted",
        "from_account": from_account,
        "to_account": to_account,
        "amount": round(amount, 2),
        "confirmation": confirmation,
        "estimated_post": "immediately",
    }


TOOLS = [
    search_banking_docs,
    find_customer,
    account_lookup,
    recent_transactions,
    find_branch,
    transfer_funds,
]
