"""Unit tests for src.inbox_tool.py.

Tests cover the retry logic in _request() and the chat_id coercion
behavior of get_imessage_thread(). urllib.request.urlopen is mocked
so no real network calls are made.
"""
import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

from src.inbox_tool import _request, get_imessage_thread, InboxError


def _make_fake_response(payload):
    """Build a context-manager mock that mimics urllib's response object."""
    body = json.dumps(payload).encode("utf-8")
    fake = MagicMock()
    fake.read.return_value = body
    fake.__enter__.return_value = fake
    fake.__exit__.return_value = False
    return fake


class TestRequestRetryLogic(unittest.TestCase):
    """Exercise the retry/back-off behavior of _request()."""

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_urlerror_retries_three_times_then_raises(self, mock_urlopen):
        """URLError must trigger 3 attempts before surfacing as InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            _request("http://example.com/api/endpoint")

        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_urlerror_does_not_raise_other_exception(self, mock_urlopen):
        """After exhausting retries the wrapper must re-raise as InboxError,
        not propagate the raw URLError."""
        mock_urlopen.side_effect = URLError("dns lookup failed")

        try:
            _request("http://example.com/api/endpoint")
        except InboxError:
            pass  # expected
        except URLError as exc:
            self.fail(f"raw URLError leaked from _request: {exc}")
        else:
            self.fail("InboxError was not raised after retries were exhausted")

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_httperror_raises_inboxerror_immediately(self, mock_urlopen):
        """HTTPError is a non-retryable failure: must raise on the first hit."""
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

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_httperror_404_raises_immediately(self, mock_urlopen):
        """A 404 should also short-circuit and not be retried."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.com/api/missing",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("http://example.com/api/missing")

        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_success_after_transient_urlerror(self, mock_urlopen):
        """If urlopen recovers within the retry budget, the result is returned."""
        fake_response = _make_fake_response({"ok": True, "messages": []})
        mock_urlopen.side_effect = [URLError("transient"), fake_response]

        # Should not raise.
        result = _request("http://example.com/api/endpoint")

        self.assertEqual(mock_urlopen.call_count, 2)
        # The decoded payload should make it back to the caller.
        self.assertEqual(result, {"ok": True, "messages": []})


class TestGetIMessageThreadChatId(unittest.TestCase):
    """get_imessage_thread must accept chat_id as either int or str."""

    @patch("src.inbox_tool._request")
    def test_accepts_integer_chat_id(self, mock_request):
        """An integer chat_id should be passed through without TypeError."""
        mock_request.return_value = {"chat_id": 42, "messages": []}

        result = get_imessage_thread(42)

        mock_request.assert_called_once()
        # The chat_id (in some form) must end up in the call to _request.
        rendered = str(mock_request.call_args)
        self.assertIn("42", rendered)
        self.assertEqual(result, {"chat_id": 42, "messages": []})

    @patch("src.inbox_tool._request")
    def test_accepts_string_chat_id(self, mock_request):
        """A string chat_id should be passed through without TypeError."""
        mock_request.return_value = {"chat_id": "abc-123", "messages": []}

        result = get_imessage_thread("abc-123")

        mock_request.assert_called_once()
        rendered = str(mock_request.call_args)
        self.assertIn("abc-123", rendered)
        self.assertEqual(result, {"chat_id": "abc-123", "messages": []})

    @patch("src.inbox_tool._request")
    def test_int_and_str_yield_equivalent_calls(self, mock_request):
        """Passing 7 and '7' should produce semantically equivalent _request calls."""
        mock_request.return_value = {}

        get_imessage_thread(7)
        int_call = mock_request.call_args

        mock_request.reset_mock()
        get_imessage_thread("7")
        str_call = mock_request.call_args

        # Strip the difference in literal type — the URL itself should match.
        self.assertEqual(
            str(int_call).replace("(7,", "(7,").replace("'7'", "7"),
            str(str_call).replace("'7'", "7"),
        )


if __name__ == "__main__":
    unittest.main()
