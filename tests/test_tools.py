import unittest
from unittest.mock import patch

from concierge.tools import TRANSACTIONS, recent_transactions


def _txs(n: int) -> list[dict]:
    return [
        {"date": f"2026-01-{i % 28 + 1:02d}", "description": f"TX {i}", "amount": -1.0, "type": "debit"}
        for i in range(n)
    ]


class RecentTransactionsTest(unittest.TestCase):
    def _call(self, txs: list[dict], limit: int) -> dict:
        with patch.dict(TRANSACTIONS, {"CUST-0001": txs}):
            return recent_transactions.invoke({"customer_id": "CUST-0001", "limit": limit})

    def test_oversized_limit_returns_full_short_history(self):
        result = self._call(_txs(7), 200)
        self.assertEqual(len(result["transactions"]), 7)
        self.assertEqual(result["returned"], 7)
        self.assertEqual(result["total_available"], 7)
        self.assertEqual(result["limit_requested"], 200)
        self.assertEqual(result["limit_applied"], 50)
        self.assertEqual(result["customer_id"], "CUST-0001")

    def test_limit_below_cap_with_fewer_available(self):
        result = self._call(_txs(3), 10)
        self.assertEqual(len(result["transactions"]), 3)
        self.assertEqual(result["returned"], 3)
        self.assertEqual(result["total_available"], 3)
        self.assertEqual(result["limit_requested"], 10)
        self.assertEqual(result["limit_applied"], 10)

    def test_limit_below_cap_with_more_available(self):
        txs = _txs(8)
        result = self._call(txs, 5)
        self.assertEqual(result["transactions"], txs[:5])
        self.assertEqual(result["returned"], 5)
        self.assertEqual(result["total_available"], 8)

    def test_oversized_limit_caps_long_history(self):
        result = self._call(_txs(80), 200)
        self.assertEqual(len(result["transactions"]), 50)
        self.assertEqual(result["returned"], 50)
        self.assertEqual(result["total_available"], 80)
        self.assertEqual(result["limit_applied"], 50)

    def test_nonpositive_limit_raises(self):
        for limit in (0, -3):
            with self.assertRaisesRegex(ValueError, "limit must be positive"):
                recent_transactions.invoke({"customer_id": "CUST-0001", "limit": limit})

    def test_unknown_customer_raises(self):
        with self.assertRaisesRegex(ValueError, "No customer found"):
            recent_transactions.invoke({"customer_id": "CUST-9999", "limit": 5})


if __name__ == "__main__":
    unittest.main()
