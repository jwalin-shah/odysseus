"""Unit tests for src/inbox_tool.py.

Covers:
* Retry behaviour of the internal ``_request()`` helper (URLError vs HTTPError).
* Type flexibility of ``get_imessage_thread()`` (accepts ``int`` and ``str``).
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

# Make the src/ folder importable regardless of where the tests are run from.
_SRC_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "src")
)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from inbox_tool import InboxError, _request, get_imessage_thread  # noqa: E402


class RequestRetryTests(unittest.TestCase):
    """Verify the retry / fail-fast behaviour of ``_request()``."""

    @patch("inbox_tool.urllib.request.urlopen")
    def test_urlerror_triggers_three_attempts_then_raises_inboxerror(self, mock_urlopen):
        """URLError should be retried 3 times before raising InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            _request("https://api.example.com/threads/1")

        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("inbox_tool.urllib.request.urlopen")
    def test_httperror_raises_inboxerror_without_retry(self, mock_urlopen):
        """HTTPError should raise InboxError immediately — no retries."""
        mock_urlopen.side_effect = HTTPError(
            url="https://api.example.com/threads/1",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("https://api.example.com/threads/1")

        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("inbox_tool.urllib.request.urlopen")
    def test_successful_response_is_returned_parsed(self, mock_urlopen):
        """A 2xx response should be returned as the parsed JSON payload."""
        payload = json.dumps({"messages": [{"id": 1, "text": "hi"}]})
        response = MagicMock()
        response.read.return_value = payload.encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        mock_urlopen.return_value = response

        result = _request("https://api.example.com/threads/1")

        self.assertEqual(result, {"messages": [{"id": 1, "text": "hi"}]})
        self.assertEqual(mock_urlopen.call_count, 1)


class GetIMessageThreadChatIdTests(unittest.TestCase):
    """Verify ``get_imessage_thread`` works with both int and str chat_ids."""

    def setUp(self):
        # Stub out _request so the test focuses purely on argument handling
        # and never hits the network.
        patcher = patch("inbox_tool._request", return_value={"thread": []})
        self.mock_request = patcher.start()
        self.addCleanup(patcher.stop)

    def test_accepts_integer_chat_id(self):
        get_imessage_thread(42)

        self.mock_request.assert_called_once()
        url = self.mock_request.call_args[0][0]
        self.assertIn("42", url)

    def test_accepts_string_chat_id(self):
        get_imessage_thread("chat_abc_123")

        self.mock_request.assert_called_once()
        url = self.mock_request.call_args[0][0]
        self.assertIn("chat_abc_123", url)


if __name__ == "__main__":
    unittest.main()
