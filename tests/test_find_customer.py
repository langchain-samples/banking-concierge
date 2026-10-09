from concierge.mock_data import CUSTOMERS
from concierge.prompts import SYSTEM_PROMPT
from concierge.tools import TOOLS, account_lookup, find_customer


def ids(**kwargs):
    return [m["customer_id"] for m in find_customer.invoke(kwargs)]


def test_ssn_match():
    assert ids(ssn="552-66-3344") == ["CUST-0005"]
    assert ids(ssn="552663344") == ["CUST-0005"]


def test_phone_match_normalized():
    assert ids(phone="512.555.0188") == ["CUST-0005"]
    assert ids(phone="+1 (512) 555-0188") == ["CUST-0005"]


def test_email_match():
    assert ids(email="Priya.Shah@example.com") == ["CUST-0002"]


def test_full_card_match():
    assert ids(card_number="6011 1111 1111 1117") == ["CUST-0005"]
    assert ids(card_number="378282246310005") == ["CUST-0004"]


def test_card_last_four_match():
    assert ids(card_number="1881") == ["CUST-0002"]


def test_account_id_match():
    assert ids(account_id="1234") == ["CUST-0001"]


def test_name_match_case_insensitive():
    assert ids(name="maya PATEL") == ["CUST-0005"]


def test_no_match():
    assert ids(ssn="000-00-0000") == []
    assert ids() == []


def test_ambiguous_returns_multiple_candidates(monkeypatch):
    twin = {**CUSTOMERS["CUST-0005"], "customer_id": "CUST-0099"}
    monkeypatch.setitem(CUSTOMERS, "CUST-0099", twin)
    assert ids(name="Maya Patel") == ["CUST-0005", "CUST-0099"]


def test_results_only_expose_id_and_name():
    for match in find_customer.invoke({"name": "Sam Okonkwo"}):
        assert set(match) == {"customer_id", "name"}


def test_find_then_account_lookup():
    [match] = find_customer.invoke({"ssn": "552-66-3344"})
    record = account_lookup.invoke({"customer_id": match["customer_id"]})
    assert record["name"] == "Maya Patel"


def test_find_customer_registered():
    assert find_customer in TOOLS


def test_account_lookup_documents_format():
    assert "CUST-####" in account_lookup.description
    assert "find_customer" in account_lookup.description


def test_prompt_directs_find_customer_first():
    assert "find_customer first" in SYSTEM_PROMPT
