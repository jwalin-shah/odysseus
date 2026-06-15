"""Unit tests for src.inbox_tool.

Covers the retry logic in _request() and the chat_id type flexibility of
get_imessage_thread(). urllib.request.urlopen is mocked in every test so no
real network I/O is performed.
"""

import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from src.inbox_tool import InboxError, _request, get_imessage_thread


def _make_response(payload):
    """Build a MagicMock that mimics urllib's context-manager response."""
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    # MagicMock already supports the context-manager protocol; the
    # __enter__/__exit__ attributes are MagicMocks themselves which is fine
    # for the purposes of these tests.
    return response


class TestRequestRetryLogic(unittest.TestCase):
    """_request() must retry transient URLErrors and fail fast on HTTPErrors."""

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_urlerror_retries_three_times_then_raises(self, mock_urlopen):
        """A persistent URLError should be retried 3 times before raising."""
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            _request("/some/path")

        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_urlerror_eventually_succeeds(self, mock_urlopen):
        """If a transient URLError resolves, the call should return the payload."""
        success_response = _make_response({"ok": True})
        mock_urlopen.side_effect = [
            URLError("blip 1"),
            URLError("blip 2"),
            success_response,
        ]

        result = _request("/some/path")

        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(result, {"ok": True})

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_httperror_raises_immediately_no_retry(self, mock_urlopen):
        """HTTPError is treated as a non-transient failure — no retries."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.invalid",
            code=500,
            msg="internal server error",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("/some/path")

        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_httperror_is_wrapped_in_inboxerror(self, mock_urlopen):
        """The raised exception must be InboxError, not a raw HTTPError."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.invalid",
            code=404,
            msg="not found",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError) as ctx:
            _request("/missing")

        # Make sure the underlying HTTPError is chained, not swallowed silently.
        self.assertIsInstance(ctx.exception.__cause__, HTTPError)


class TestGetImessageThreadChatId(unittest.TestCase):
    """get_imessage_thread() must accept chat_id as either int or str."""

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_accepts_int_chat_id(self, mock_urlopen):
        """An integer chat_id is accepted and stringified into the URL."""
        mock_urlopen.return_value = _make_response({"messages": []})

        get_imessage_thread(12345)

        called_url = mock_urlopen.call_args[0][0]
        # The URL (or Request) passed to urlopen must contain the chat_id
        # as its string form.
        self.assertIn("12345", str(called_url))

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_accepts_str_chat_id(self, mock_urlopen):
        """A string chat_id is accepted and embedded verbatim into the URL."""
        mock_urlopen.return_value = _make_response({"messages": []})

        get_imessage_thread("chat-abc-123")

        called_url = mock_urlopen.call_args[0][0]
        self.assertIn("chat-abc-123", str(called_url))

    @patch("src.inbox_tool.urllib.request.urlopen")
    def test_int_and_str_produce_same_url(self, mock_urlopen):
        """int(123) and str('123') should hit the same endpoint."""
        mock_urlopen.return_value = _make_response({"messages": []})

        get_imessage_thread(123)
        url_from_int = str(mock_urlopen.call_args[0][0])

        get_imessage_thread("123")
        url_from_str = str(mock_urlopen.call_args[0][0])

        self.assertEqual(url_from_int, url_from_str)


if __name__ == "__main__":
    unittest.main()
