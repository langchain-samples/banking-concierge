"""Tests for input-side PII redaction and the trace anonymizer."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from concierge.redaction import (  # noqa: E402
    redact_messages,
    redact_text,
    trace_anonymizer,
)

SSN = "552-19-4488"
PAN = "4242 4242 4242 4242"
PASTED = (
    f"Customer details: Alex Rivera, SSN {SSN}, Visa {PAN} exp 08/29 CVV 314. "
    "Open a new savings account."
)


def test_formatted_ssn_is_replaced():
    redacted, mapping = redact_text(f"Customer's SSN is {SSN}, verify them")
    assert redacted == "Customer's SSN is [SSN_1], verify them"
    assert mapping == {"[SSN_1]": SSN}


def test_labeled_contiguous_ssn_is_replaced():
    redacted, mapping = redact_text("social security number: 552194488")
    assert redacted == "social security number: [SSN_1]"
    assert mapping == {"[SSN_1]": "552194488"}


def test_unlabeled_nine_digits_are_preserved():
    text = "Reference 552194488 on the ticket"
    assert redact_text(text) == (text, {})


def test_luhn_valid_pans_are_replaced_with_and_without_separators():
    for pan in (PAN, "4242-4242-4242-4242", "4242424242424242", "378282246310005"):
        redacted, mapping = redact_text(f"card {pan} disputed")
        assert redacted == "card [CARD_1] disputed"
        assert mapping == {"[CARD_1]": pan}


def test_non_luhn_digit_sequences_are_preserved():
    text = "Confirmation 4242 4242 4242 4241 and ref 1234567890123"
    assert redact_text(text) == (text, {})


def test_labeled_cvvs_are_replaced():
    assert redact_text("CVV 314") == ("CVV [CVV_1]", {"[CVV_1]": "314"})
    assert redact_text("security code: 1234") == (
        "security code: [CVV_1]",
        {"[CVV_1]": "1234"},
    )
    assert redact_text("cvc is 987") == ("cvc is [CVV_1]", {"[CVV_1]": "987"})


def test_unrelated_text_is_unchanged():
    text = "What is the monthly fee on Everyday Checking? Customer CUST-0001, zip 94105."
    assert redact_text(text) == (text, {})


def test_multiple_values_map_to_matching_placeholders():
    redacted, mapping = redact_text(PASTED)
    assert redacted == (
        "Customer details: Alex Rivera, SSN [SSN_1], Visa [CARD_1] exp [EXP_1] "
        "CVV [CVV_1]. Open a new savings account."
    )
    assert mapping == {
        "[SSN_1]": SSN,
        "[CARD_1]": PAN,
        "[EXP_1]": "08/29",
        "[CVV_1]": "314",
    }


def test_existing_mapping_keeps_placeholders_stable():
    _, mapping = redact_text(f"SSN {SSN}")
    redacted, mapping = redact_text(f"again {SSN}, spouse 123-45-6789", mapping)
    assert redacted == "again [SSN_1], spouse [SSN_2]"
    assert mapping == {"[SSN_1]": SSN, "[SSN_2]": "123-45-6789"}


def test_redact_messages_copies_human_turns_only():
    human = HumanMessage(content=PASTED, id="h1")
    ai = AIMessage(content=f"echo {SSN}", id="a1")
    redacted, mapping = redact_messages([human, ai])
    assert human.content == PASTED
    assert redacted[0] is not human
    assert redacted[0].id == "h1"
    assert SSN not in redacted[0].content and PAN not in redacted[0].content
    assert redacted[1] is ai
    assert mapping["[SSN_1]"] == SSN


def test_redact_messages_handles_content_blocks():
    human = HumanMessage(content=[{"type": "text", "text": f"card {PAN}"}])
    redacted, mapping = redact_messages([human])
    assert redacted[0].content == [{"type": "text", "text": "card [CARD_1]"}]
    assert mapping == {"[CARD_1]": PAN}


def test_trace_anonymizer_masks_nested_values():
    data = {"messages": [{"type": "human", "content": PASTED}], "pii_map": {"x": SSN}}
    masked = trace_anonymizer(data)
    serialized = repr(masked)
    for raw in (SSN, PAN, "08/29", "CVV 314"):
        assert raw not in serialized
