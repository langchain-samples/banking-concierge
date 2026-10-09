"""agent_node returns a fallback answer when the model provider rejects the request."""

import importlib
import unittest
from unittest import mock

import httpx
import openai
from langchain_core.messages import AIMessage, HumanMessage

graph_module = importlib.import_module("concierge.graph")

try:
    import anthropic
except ImportError:
    anthropic = None


def _status_error(error_cls, status_code: int) -> Exception:
    """Build an SDK status error the way the provider client raises it."""
    request = httpx.Request("POST", "https://example.invalid/v1/chat")
    response = httpx.Response(status_code, request=request)
    return error_cls(f"Error code: {status_code}", response=response, body=None)


class AgentNodeProviderErrorTest(unittest.TestCase):
    def _run(self, exc: Exception) -> dict:
        model = mock.Mock()
        model.invoke.side_effect = exc
        state = {
            "messages": [HumanMessage("What is the monthly fee?")],
            "retrieval_calls": 3,
        }
        with mock.patch.object(graph_module, "_make_model", return_value=model):
            return graph_module.agent_node(state)

    def _assert_fallback(self, exc: Exception) -> None:
        with self.assertLogs(graph_module.logger, level="ERROR"):
            result = self._run(exc)
        [message] = result["messages"]
        self.assertIsInstance(message, AIMessage)
        self.assertEqual(message.content, graph_module.MODEL_UNAVAILABLE_MESSAGE)
        self.assertEqual(result["retrieval_calls"], 3)

    def test_openai_permission_denied(self):
        self._assert_fallback(_status_error(openai.PermissionDeniedError, 403))

    def test_openai_authentication_error(self):
        self._assert_fallback(_status_error(openai.AuthenticationError, 401))

    @unittest.skipIf(anthropic is None, "anthropic not installed")
    def test_anthropic_permission_denied(self):
        self._assert_fallback(_status_error(anthropic.PermissionDeniedError, 403))

    @unittest.skipIf(anthropic is None, "anthropic not installed")
    def test_anthropic_authentication_error(self):
        self._assert_fallback(_status_error(anthropic.AuthenticationError, 401))

    def test_unrelated_errors_propagate(self):
        for exc in (
            ValueError("boom"),
            _status_error(openai.InternalServerError, 500),
        ):
            with self.subTest(exc=type(exc).__name__), self.assertRaises(type(exc)):
                self._run(exc)


if __name__ == "__main__":
    unittest.main()
