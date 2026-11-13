import pytest

from concierge.prompts import SYSTEM_PROMPT
from concierge.tools import account_lookup, recent_transactions


@pytest.mark.parametrize("bad_id", ["552-77-1230", "(650) 555-0117", "CUST-12", "cust-0001"])
def test_account_lookup_rejects_malformed_id_without_claiming_absence(bad_id):
    with pytest.raises(ValueError) as exc:
        account_lookup.invoke({"customer_id": bad_id})
    message = str(exc.value)
    assert "Invalid customer ID format" in message
    assert "No lookup was performed" in message
    assert "No customer found" not in message


def test_account_lookup_well_formed_absent_id_is_not_found():
    with pytest.raises(ValueError, match="No customer found with ID 'CUST-9999'"):
        account_lookup.invoke({"customer_id": "CUST-9999"})


def test_account_lookup_outage_takes_precedence():
    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        account_lookup.invoke({"customer_id": "X-552-77-1230"})


def test_account_lookup_valid_id_returns_record():
    assert account_lookup.invoke({"customer_id": "CUST-0001"})["customer_id"] == "CUST-0001"


def test_recent_transactions_rejects_malformed_id():
    with pytest.raises(ValueError, match="No lookup was performed"):
        recent_transactions.invoke({"customer_id": "552-77-1230"})


@pytest.mark.parametrize("tool", [account_lookup, recent_transactions])
def test_tool_descriptions_state_accepted_id_format(tool):
    assert "CUST-####" in tool.description
    assert "SSNs, phone numbers, card numbers, and account" in tool.description


def test_system_prompt_forbids_inferring_absence_from_failed_lookup():
    assert "never tell the representative the customer does not exist" in SYSTEM_PROMPT
    assert "what identifier you need" in SYSTEM_PROMPT
