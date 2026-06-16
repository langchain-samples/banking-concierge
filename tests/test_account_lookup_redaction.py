"""Tests for PII redaction at the account_lookup tool boundary."""

from __future__ import annotations

import json
import re

from concierge.tools import account_lookup, get_card_last4, get_ssn_last4

SSN_PATTERN = re.compile(r"\d{3}-\d{2}-\d{4}")
LONG_DIGIT_RUN = re.compile(r"\d{13,}")


def _invoke(tool, **kwargs):
    return tool.invoke(kwargs)


def test_account_lookup_omits_raw_ssn_and_cvv():
    result = _invoke(account_lookup, customer_id="CUST-0001")

    assert "ssn" not in result
    assert "ssn_masked" in result
    assert result["ssn_masked"] == "***-**-4488"

    for card in result["credit_cards"]:
        assert "cvv" not in card
        assert "exp" not in card
        assert card["number"] == "****-****-****-4242"


def test_account_lookup_response_contains_no_full_ssn_or_pan():
    result = _invoke(account_lookup, customer_id="CUST-0001")
    blob = json.dumps(result)

    assert not SSN_PATTERN.search(blob)
    assert not LONG_DIGIT_RUN.search(re.sub(r"\D", "", blob)) or all(
        not LONG_DIGIT_RUN.search(str(v)) for v in _flatten(result)
    )


def _flatten(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _flatten(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _flatten(v)
    else:
        yield obj


def test_get_ssn_last4_returns_only_last_four():
    assert _invoke(get_ssn_last4, customer_id="CUST-0001") == "4488"


def test_get_card_last4_returns_only_last_four():
    assert _invoke(get_card_last4, customer_id="CUST-0001") == "4242"
