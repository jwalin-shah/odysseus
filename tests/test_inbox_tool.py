"""Unit tests for src/inbox_tool.py.

Covers:
- Retry behaviour of _request() on URLError (3 attempts, then InboxError).
- Immediate InboxError on HTTPError (no retry).
- get_imessage_thread() accepting both int and str chat_id.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

# Make the src/ package importable when running this file directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_tool import InboxError, _request, get_imessage_thread  # noqa: E402


class TestRequestRetryLogic(unittest.TestCase):
    """Tests the retry policy of the private _request helper."""

    @patch("inbox_tool.urllib.request.urlopen")
    def test_urlerror_retries_three_times_then_raises(self, mock_urlopen):
        """On URLError, _request should attempt 3 times then raise InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            _request("http://example.com/api/endpoint")

        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("inbox_tool.urllib.request.urlopen")
    def test_httperror_raises_immediately_no_retry(self, mock_urlopen):
        """On HTTPError, _request should raise InboxError without retrying."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.com/api/endpoint",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("http://example.com/api/endpoint")

        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("inbox_tool.urllib.request.urlopen")
    def test_urlerror_recovers_on_subsequent_attempt(self, mock_urlopen):
        """A successful response after a transient URLError should be returned."""
        good_response = MagicMock()
        good_response.read.return_value = b'{"ok": true}'
        good_response.status = 200
        # First attempt fails, second succeeds.
        mock_urlopen.side_effect = [URLError("transient"), good_response]

        result = _request("http://example.com/api/endpoint")

        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertIsNotNone(result)


class TestGetIMessageThread(unittest.TestCase):
    """Tests that get_imessage_thread accepts both int and str chat_id values."""

    @patch("inbox_tool._request")
    def test_accepts_int_chat_id(self, mock_request):
        """An int chat_id should be accepted without raising TypeError."""
        mock_request.return_value = {"messages": []}

        result = get_imessage_thread(12345)

        mock_request.assert_called_once()
        self.assertEqual(result, {"messages": []})

    @patch("inbox_tool._request")
    def test_accepts_str_chat_id(self, mock_request):
        """A str chat_id should be accepted without raising TypeError."""
        mock_request.return_value = {"messages": []}

        result = get_imessage_thread("12345")

        mock_request.assert_called_once()
        self.assertEqual(result, {"messages": []})

    @patch("inbox_tool._request")
    def test_int_and_str_chat_id_produce_equivalent_request(self, mock_request):
        """Both int and str chat_id should produce an equivalent underlying request."""
        mock_request.return_value = {"messages": []}

        get_imessage_thread(12345)
        int_call_repr = str(mock_request.call_args)

        mock_request.reset_mock()
        get_imessage_thread("12345")
        str_call_repr = str(mock_request.call_args)

        # The same chat identifier should appear in both invocations.
        self.assertIn("12345", int_call_repr)
        self.assertIn("12345", str_call_repr)


if __name__ == "__main__":
    unittest.main()
