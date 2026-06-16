"""Tests that account_lookup redacts PCI-regulated cardholder data and SSN."""

from __future__ import annotations

from concierge.mock_data import CUSTOMERS
from concierge.tools import _redact_customer, account_lookup


def test_redact_customer_strips_cvv_and_full_pan():
    customer = CUSTOMERS["CUST-0001"]
    redacted = _redact_customer(customer)
    for card in redacted["credit_cards"]:
        assert "cvv" not in card
        assert "number" not in card
        assert card["number_last4"] == customer["credit_cards"][0]["number"][-4:]


def test_redact_customer_masks_ssn():
    customer = CUSTOMERS["CUST-0001"]
    redacted = _redact_customer(customer)
    assert redacted["ssn"] == "***-**-4488"


def test_redact_customer_handles_missing_ssn():
    redacted = _redact_customer({"name": "Nobody", "credit_cards": []})
    assert "ssn" not in redacted or redacted["ssn"] == ""


def test_account_lookup_does_not_leak_pan_or_cvv():
    result = account_lookup.invoke({"customer_id": "CUST-0001"})
    serialized = repr(result)
    assert "4242 4242 4242 4242" not in serialized
    assert "cvv" not in serialized.lower()
    for card in result["credit_cards"]:
        assert "cvv" not in card
        assert "number" not in card
        assert "number_last4" in card
    assert result["ssn"].startswith("***-**-")
