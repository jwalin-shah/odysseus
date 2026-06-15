"""Unit tests for src/inbox_tool.py.

Covers:
  * Retry behavior of _request() — 3 retries on URLError, no retry on HTTPError.
  * get_imessage_thread() accepting both int and str chat_id.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

# Make the src/ package importable when tests are run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_tool import _request, get_imessage_thread, InboxError  # noqa: E402


def _make_response(body: bytes = b'{"ok": true}') -> MagicMock:
    """Build a mock object that quacks like the return value of urlopen()."""
    resp = MagicMock()
    resp.read.return_value = body
    return resp


class TestRequestRetryLogic(unittest.TestCase):
    """Tests for the retry behavior implemented in _request()."""

    @patch("inbox_tool.urlopen")
    def test_urlerror_retries_three_times_then_raises(self, mock_urlopen):
        """URLError should trigger exactly 3 attempts before raising InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        self.assertEqual(
            mock_urlopen.call_count,
            3,
            "urlopen should be called 3 times (initial + 2 retries) on URLError",
        )

    @patch("inbox_tool.urlopen")
    def test_urlerror_recovers_on_third_attempt(self, mock_urlopen):
        """If a later retry succeeds, _request should return its result."""
        mock_urlopen.side_effect = [
            URLError("transient 1"),
            URLError("transient 2"),
            _make_response(b'{"thread": "data"}'),
        ]

        result = _request("http://example.com/api")

        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(result, {"thread": "data"})

    @patch("inbox_tool.urlopen")
    def test_urlerror_fails_after_three_attempts(self, mock_urlopen):
        """After 3 URLErrors, no more attempts should be made."""
        mock_urlopen.side_effect = URLError("always fails")

        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        # Exactly 3 attempts, never a 4th.
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("inbox_tool.urlopen")
    def test_httperror_no_retry(self, mock_urlopen):
        """HTTPError should raise InboxError immediately with no retry."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.com/api",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        # HTTPError is a deterministic client/server failure — no retry.
        self.assertEqual(
            mock_urlopen.call_count,
            1,
            "urlopen should be called exactly once for HTTPError (no retry)",
        )

    @patch("inbox_tool.urlopen")
    def test_httperror_404_raises_without_retry(self, mock_urlopen):
        """A 404 HTTPError is also non-retriable."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.com/missing",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("http://example.com/missing")

        self.assertEqual(mock_urlopen.call_count, 1)


class TestGetImessageThreadChatId(unittest.TestCase):
    """Tests that get_imessage_thread() normalizes int and str chat_id values."""

    @patch("inbox_tool.urlopen")
    def test_accepts_int_chat_id(self, mock_urlopen):
        """get_imessage_thread should work with an integer chat_id."""
        mock_urlopen.return_value = _make_response(b'{"thread": []}')

        result = get_imessage_thread(12345)

        self.assertEqual(mock_urlopen.call_count, 1)
        # The numeric chat_id should appear somewhere in the request payload.
        self.assertIn("12345", str(mock_urlopen.call_args))

    @patch("inbox_tool.urlopen")
    def test_accepts_str_chat_id(self, mock_urlopen):
        """get_imessage_thread should work with a string chat_id."""
        mock_urlopen.return_value = _make_response(b'{"thread": []}')

        result = get_imessage_thread("12345")

        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertIn("12345", str(mock_urlopen.call_args))

    @patch("inbox_tool.urlopen")
    def test_int_and_str_chat_id_produce_equivalent_request(self, mock_urlopen):
        """int(12345) and str('12345') should produce the same outgoing request."""
        mock_urlopen.return_value = _make_response(b'{"thread": []}')

        get_imessage_thread(12345)
        int_call = str(mock_urlopen.call_args)

        mock_urlopen.reset_mock()
        mock_urlopen.return_value = _make_response(b'{"thread": []}')

        get_imessage_thread("12345")
        str_call = str(mock_urlopen.call_args)

        # Both representations should end up in the same shape of request.
        self.assertEqual(int_call, str_call)

    @patch("inbox_tool.urlopen")
    def test_returns_parsed_response(self, mock_urlopen):
        """get_imessage_thread should return the parsed JSON payload."""
        mock_urlopen.return_value = _make_response(
            b'{"thread": [{"id": 1, "text": "hi"}]}'
        )

        result = get_imessage_thread(42)

        self.assertEqual(result, {"thread": [{"id": 1, "text": "hi"}]})


if __name__ == "__main__":
    unittest.main()
