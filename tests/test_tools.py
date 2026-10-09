"""Tests that customer-data tools never expose full SSNs, card numbers, or CVVs."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from concierge.mock_data import CUSTOMERS
from concierge.prompts import SYSTEM_PROMPT
from concierge.tools import TOOLS, account_lookup, verify_identity

PII_DATASET = Path(__file__).resolve().parents[1] / "evals" / "dataset_pii.json"


def _sensitive_values(customer_id: str) -> list[str]:
    customer = CUSTOMERS[customer_id]
    values = [customer["ssn"], customer["ssn"].replace("-", "")]
    for card in customer["credit_cards"]:
        values += [card["number"], card["number"].replace(" ", "")]
    return values


def _cvvs(customer_id: str) -> list[str]:
    return [card["cvv"] for card in CUSTOMERS[customer_id]["credit_cards"]]


class AccountLookupTest(unittest.TestCase):
    def test_returns_allowed_fields_without_sensitive_values(self) -> None:
        result = account_lookup.invoke({"customer_id": "CUST-0001"})
        customer = CUSTOMERS["CUST-0001"]
        self.assertEqual(
            set(result),
            {"customer_id", "name", "ssn_last4", "phone", "email", "credit_cards", "accounts"},
        )
        self.assertEqual(result["name"], customer["name"])
        self.assertEqual(result["phone"], customer["phone"])
        self.assertEqual(result["email"], customer["email"])
        self.assertEqual(result["accounts"], customer["accounts"])
        self.assertEqual(result["ssn_last4"], "4488")
        self.assertEqual(
            result["credit_cards"], [{"brand": "Visa", "last4": "4242", "exp": "08/29"}]
        )
        serialized = json.dumps(result)
        for value in _sensitive_values("CUST-0001"):
            self.assertNotIn(value, serialized)

    def test_sanitizes_every_card(self) -> None:
        for customer_id in ("CUST-0002", "CUST-0004"):
            result = account_lookup.invoke({"customer_id": customer_id})
            cards = CUSTOMERS[customer_id]["credit_cards"]
            self.assertEqual(len(result["credit_cards"]), len(cards))
            for returned, stored in zip(result["credit_cards"], cards):
                self.assertEqual(set(returned), {"brand", "last4", "exp"})
                self.assertEqual(returned["last4"], stored["number"].replace(" ", "")[-4:])
            serialized = json.dumps(result)
            for value in _sensitive_values(customer_id):
                self.assertNotIn(value, serialized)
            self.assertNotIn("cvv", serialized.lower())


class VerifyIdentityTest(unittest.TestCase):
    def _assert_no_values(self, result: dict, *values: str) -> None:
        serialized = json.dumps(result)
        for value in values:
            self.assertNotIn(value, serialized)

    def test_ssn_last4_match_and_mismatch(self) -> None:
        match = verify_identity.invoke({"customer_id": "CUST-0002", "ssn_last4": "8810"})
        self.assertTrue(match["ssn_last4_match"])
        mismatch = verify_identity.invoke({"customer_id": "CUST-0002", "ssn_last4": "1111"})
        self.assertFalse(mismatch["ssn_last4_match"])
        for result in (match, mismatch):
            self.assertEqual(set(result), {"customer_id", "ssn_last4_match", "card_last4_match"})
            self._assert_no_values(result, "8810", "1111", *_sensitive_values("CUST-0002"))

    def test_card_last4_match_and_mismatch(self) -> None:
        match = verify_identity.invoke({"customer_id": "CUST-0002", "card_last4": "1881"})
        self.assertTrue(match["card_last4_match"])
        mismatch = verify_identity.invoke({"customer_id": "CUST-0002", "card_last4": "9999"})
        self.assertFalse(mismatch["card_last4_match"])
        for result in (match, mismatch):
            self._assert_no_values(result, "1881", "9999", *_sensitive_values("CUST-0002"))
            for cvv in _cvvs("CUST-0002"):
                self.assertNotIn(cvv, json.dumps(result))

    def test_omitted_inputs_report_no_result(self) -> None:
        result = verify_identity.invoke({"customer_id": "CUST-0001"})
        self.assertEqual(
            result,
            {"customer_id": "CUST-0001", "ssn_last4_match": None, "card_last4_match": None},
        )

    def test_unknown_customer_raises(self) -> None:
        with self.assertRaises(ValueError):
            verify_identity.func("CUST-9999", ssn_last4="4488")


class RegistryAndPromptTest(unittest.TestCase):
    def test_tools_registry_exposes_verify_identity(self) -> None:
        self.assertIn("verify_identity", {t.name for t in TOOLS})

    def test_prompt_forbids_full_readback_and_uses_last4_verification(self) -> None:
        self.assertNotIn("verbatim", SYSTEM_PROMPT)
        self.assertIn("Never state a full SSN, full card number, or CVV", SYSTEM_PROMPT)
        self.assertIn("verify_identity", SYSTEM_PROMPT)

    def test_pii_dataset_expects_no_full_readback(self) -> None:
        dataset = json.loads(PII_DATASET.read_text())
        comments = [
            assertion["comment"]
            for example in dataset["examples"]
            for assertion in example["outputs"]["assertions"]
        ]
        self.assertTrue(comments)
        for comment in comments:
            self.assertNotIn("account_lookup", comment)
        self.assertTrue(any("only the last four digits may appear" in c for c in comments))


if __name__ == "__main__":
    unittest.main()
