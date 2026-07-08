"""Tests for the transfer_funds tool's customer-ownership verification."""

from __future__ import annotations

import pytest

from concierge.mock_data import CUSTOMERS
from concierge.tools import transfer_funds


def _invoke(**kwargs):
    return transfer_funds.invoke(kwargs)


def test_transfer_succeeds_when_both_accounts_belong_to_customer():
    result = _invoke(
        customer_id="CUST-0001",
        from_account="1234",
        to_account="5678",
        amount=25.0,
    )
    assert result["status"] == "submitted"
    assert result["customer_id"] == "CUST-0001"
    assert result["from_account"] == "1234"
    assert result["to_account"] == "5678"
    assert result["amount"] == 25.0
    assert result["confirmation"].startswith("MNB-XFER-")


def test_transfer_response_includes_customer_and_account_type_fields():
    owned = {a["account_id"]: a for a in CUSTOMERS["CUST-0001"]["accounts"]}
    result = _invoke(
        customer_id="CUST-0001",
        from_account="1234",
        to_account="5678",
        amount=10.0,
    )
    assert result["customer_id"] == "CUST-0001"
    assert result["from_account_type"] == owned["1234"]["type"]
    assert result["to_account_type"] == owned["5678"]["type"]


def test_transfer_rejects_unknown_customer_id():
    with pytest.raises(ValueError, match="No customer found"):
        _invoke(
            customer_id="CUST-9999",
            from_account="1234",
            to_account="5678",
            amount=10.0,
        )


def test_transfer_rejects_from_account_not_owned_by_customer():
    with pytest.raises(ValueError, match="does not belong to customer"):
        _invoke(
            customer_id="CUST-0001",
            from_account="2233",
            to_account="5678",
            amount=10.0,
        )


def test_transfer_rejects_to_account_not_owned_by_customer():
    with pytest.raises(ValueError, match="does not belong to customer"):
        _invoke(
            customer_id="CUST-0001",
            from_account="1234",
            to_account="4455",
            amount=10.0,
        )


def test_transfer_still_rejects_non_positive_amount():
    with pytest.raises(ValueError, match="amount must be positive"):
        _invoke(
            customer_id="CUST-0001",
            from_account="1234",
            to_account="5678",
            amount=0,
        )
