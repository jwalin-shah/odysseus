"""Unit tests for src.inbox_tool.

Covers:
- _request() retry behaviour for URLError (3 retries) and HTTPError (no retry)
- get_imessage_thread() accepting both int and str chat_id
"""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

# Ensure the project root is on sys.path so we can import `src.inbox_tool`.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.inbox_tool import InboxError, InboxTool  # noqa: E402


def _make_json_response(payload):
    """Build a context-manager mock that returns JSON ``payload`` from .read()."""
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


class TestRequestRetryLogic(unittest.TestCase):
    """Verify _request() retry semantics for network errors."""

    def setUp(self):
        self.tool = InboxTool(base_url="http://test.local")

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_urlerror_retries_three_times_then_raises(self, mock_urlopen):
        """URLError should trigger exactly 3 attempts before raising InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            self.tool._request("/endpoint")

        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_urlerror_eventually_succeeds_within_retry_window(self, mock_urlopen):
        """A successful response within the retry window is returned to the caller."""
        mock_urlopen.side_effect = [
            URLError("transient 1"),
            URLError("transient 2"),
            _make_json_response({"ok": True}),
        ]

        result = self.tool._request("/endpoint")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_httperror_raises_inbox_error_immediately(self, mock_urlopen):
        """HTTPError should not be retried; InboxError raised on the first failure."""
        mock_urlopen.side_effect = HTTPError(
            url="http://test.local/endpoint",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            self.tool._request("/endpoint")

        # Crucially: no retries on HTTPError.
        self.assertEqual(mock_urlopen.call_count, 1)


class TestGetIMessageThread(unittest.TestCase):
    """Verify get_imessage_thread() handles int and str chat_id values."""

    def setUp(self):
        self.tool = InboxTool(base_url="http://test.local")

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_get_imessage_thread_with_int_chat_id(self, mock_urlopen):
        """An int chat_id is normalised to its string form in the request URL."""
        mock_urlopen.return_value = _make_json_response(
            {"chat_id": 12345, "messages": []}
        )

        result = self.tool.get_imessage_thread(12345)

        self.assertEqual(result, {"chat_id": 12345, "messages": []})
        mock_urlopen.assert_called_once()
        called_request = mock_urlopen.call_args[0][0]
        self.assertIn("12345", called_request.full_url)

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_get_imessage_thread_with_str_chat_id(self, mock_urlopen):
        """A str chat_id is passed through to the request URL unchanged."""
        mock_urlopen.return_value = _make_json_response(
            {"chat_id": "chat-abc", "messages": []}
        )

        result = self.tool.get_imessage_thread("chat-abc")

        self.assertEqual(result, {"chat_id": "chat-abc", "messages": []})
        mock_urlopen.assert_called_once()
        called_request = mock_urlopen.call_args[0][0]
        self.assertIn("chat-abc", called_request.full_url)


if __name__ == "__main__":
    unittest.main()
