"""Unit tests for src/inbox_tool.py.

Covers the retry behaviour of _request() and the chat_id type
flexibility of get_imessage_thread().
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

# Make the src/ directory importable when running the tests directly.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from inbox_tool import InboxError, _request, get_imessage_thread  # noqa: E402


def _make_context_response(payload: bytes = b'{"messages": []}'):
    """Build a MagicMock that behaves like a urlopen context manager."""
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    return response


class TestRequestRetryLogic(unittest.TestCase):
    """Tests for the internal _request() helper."""

    @patch("urllib.request.urlopen")
    def test_urlerror_retries_three_times_then_raises(self, mock_urlopen):
        """A persistent URLError must be retried exactly 3 times."""
        mock_urlopen.side_effect = URLError("simulated network failure")

        with self.assertRaises(InboxError):
            _request("http://example.invalid/api")

        self.assertEqual(
            mock_urlopen.call_count,
            3,
            "Expected _request to retry 3 times before giving up",
        )

    @patch("urllib.request.urlopen")
    def test_urlerror_succeeds_on_retry(self, mock_urlopen):
        """A successful response on a later attempt should not raise."""
        good_response = _make_context_response(b'{"ok": true}')
        # Fail twice, then succeed on the third attempt.
        mock_urlopen.side_effect = [
            URLError("transient"),
            URLError("transient"),
            good_response,
        ]

        result = _request("http://example.invalid/api")

        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(result.read(), b'{"ok": true}')

    @patch("urllib.request.urlopen")
    def test_httperror_raises_immediately_no_retry(self, mock_urlopen):
        """HTTPError must surface as InboxError after a single attempt."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.invalid/api",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("http://example.invalid/api")

        self.assertEqual(
            mock_urlopen.call_count,
            1,
            "HTTPError must not trigger retries",
        )

    @patch("urllib.request.urlopen")
    def test_httperror_404_raises_immediately(self, mock_urlopen):
        """A 404 HTTPError is also non-retryable."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.invalid/missing",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("http://example.invalid/missing")

        self.assertEqual(mock_urlopen.call_count, 1)


class TestGetIMessageThreadChatId(unittest.TestCase):
    """get_imessage_thread should accept both int and str chat IDs."""

    @patch("urllib.request.urlopen")
    def test_accepts_integer_chat_id(self, mock_urlopen):
        """An integer chat_id must be accepted without TypeError."""
        mock_urlopen.return_value = _make_context_response(
            b'{"chat_id": 12345, "messages": []}'
        )

        # Must not raise — the previous behaviour raised TypeError on ints.
        result = get_imessage_thread(12345)

        self.assertIsNotNone(result)
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_accepts_string_chat_id(self, mock_urlopen):
        """A string chat_id must continue to work."""
        mock_urlopen.return_value = _make_context_response(
            b'{"chat_id": "12345", "messages": []}'
        )

        result = get_imessage_thread("12345")

        self.assertIsNotNone(result)
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_both_types_produce_same_url(self, mock_urlopen):
        """int and str chat_id should ultimately hit the same endpoint."""
        mock_urlopen.return_value = _make_context_response(b'{"messages": []}')

        get_imessage_thread(12345)
        get_imessage_thread("12345")

        self.assertEqual(mock_urlopen.call_count, 2)

        first_url = mock_urlopen.call_args_list[0].args[0] \
            if mock_urlopen.call_args_list[0].args \
            else mock_urlopen.call_args_list[0].kwargs.get("url", "")
        second_url = mock_urlopen.call_args_list[1].args[0] \
            if mock_urlopen.call_args_list[1].args \
            else mock_urlopen.call_args_list[1].kwargs.get("url", "")

        self.assertEqual(first_url, second_url)


if __name__ == "__main__":
    unittest.main()
