"""Unit tests for src/inbox_tool.py.

Covers:
- Retry logic in _request() for URLError and HTTPError
- get_imessage_thread() accepting both int and str chat_id
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

# Make `src/` importable when running this file directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_tool import _request, get_imessage_thread, InboxError  # noqa: E402


def _make_urlopen_response(payload: dict) -> MagicMock:
    """Build a context-manager mock that mimics urllib's response object."""
    body = MagicMock()
    body.read.return_value = str(payload).replace("'", '"').encode("utf-8")
    body.__enter__.return_value = body
    body.__exit__.return_value = False
    return body


class TestRequestRetryLogic(unittest.TestCase):
    """Tests for the retry/raise behavior of _request()."""

    @patch("urllib.request.urlopen")
    def test_urlerror_retries_three_times_then_raises_inboxerror(self, mock_urlopen):
        """URLError: _request should try 3 times total, then raise InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        self.assertEqual(
            mock_urlopen.call_count,
            3,
            "Expected exactly 3 attempts before giving up on URLError",
        )

    @patch("urllib.request.urlopen")
    def test_http_error_raises_inboxerror_immediately(self, mock_urlopen):
        """HTTPError: _request should raise InboxError on the first attempt (no retry)."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.com/api",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        self.assertEqual(
            mock_urlopen.call_count,
            1,
            "HTTPError must not trigger a retry",
        )

    @patch("urllib.request.urlopen")
    def test_success_returns_parsed_body_without_retry(self, mock_urlopen):
        """On a successful response, _request should not retry."""
        mock_urlopen.return_value = _make_urlopen_response({"ok": True})

        result = _request("http://example.com/api")

        self.assertEqual(mock_urlopen.call_count, 1)
        # Result should be the parsed payload (JSON or dict-ish); just assert truthy
        self.assertTrue(result)


class TestGetIMessageThread(unittest.TestCase):
    """Tests for get_imessage_thread() argument handling."""

    @patch("inbox_tool._request")
    def test_accepts_int_chat_id(self, mock_request):
        """get_imessage_thread should accept an integer chat_id."""
        mock_request.return_value = {"messages": []}

        result = get_imessage_thread(123)

        mock_request.assert_called_once()
        self.assertEqual(result, {"messages": []})
        # The int chat_id should appear somewhere in the call
        self.assertIn("123", str(mock_request.call_args))

    @patch("inbox_tool._request")
    def test_accepts_str_chat_id(self, mock_request):
        """get_imessage_thread should accept a string chat_id."""
        mock_request.return_value = {"messages": []}

        result = get_imessage_thread("123")

        mock_request.assert_called_once()
        self.assertEqual(result, {"messages": []})
        self.assertIn("123", str(mock_request.call_args))

    @patch("inbox_tool._request")
    def test_int_and_str_chat_id_produce_equivalent_request(self, mock_request):
        """Both int and str chat_id should yield the same underlying request URL."""
        mock_request.return_value = {"messages": []}

        get_imessage_thread(42)
        int_args = mock_request.call_args

        mock_request.reset_mock()
        get_imessage_thread("42")
        str_args = mock_request.call_args

        # The first positional argument (typically the URL) must be identical
        self.assertEqual(int_args[0][0], str_args[0][0])


if __name__ == "__main__":
    unittest.main()
