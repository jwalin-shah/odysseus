"""Unit tests for src/inbox_tool.py.

Covers:
  * Retry behaviour of _request() against URLError and HTTPError.
  * Type handling of chat_id in get_imessage_thread().

Note: src/inbox_tool.py is assumed to use ``from urllib.request import urlopen``;
adjust the patch targets if the implementation imports the module instead.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

# Make ``src`` importable when the tests are run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_tool import InboxError, _request, get_imessage_thread  # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _make_response(payload: bytes = b'{"ok": true}'):
    """Build a context-manager-compatible mock HTTP response."""
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    return response


def _extract_url(mock_urlopen) -> str:
    """Return the URL that was passed to ``urlopen`` as a plain string."""
    call_arg = mock_urlopen.call_args[0][0]
    if hasattr(call_arg, "get_full_url"):  # urllib.request.Request
        return call_arg.get_full_url()
    if hasattr(call_arg, "full_url"):
        return call_arg.full_url
    return str(call_arg)


# --------------------------------------------------------------------------- #
# Retry logic in _request()
# --------------------------------------------------------------------------- #
class TestRequestRetryLogic(unittest.TestCase):
    """Verify _request() retries on transient network errors only."""

    @patch("inbox_tool.time.sleep", return_value=None)
    @patch("inbox_tool.urlopen")
    def test_urlerror_is_retried_three_times_then_raises(self, mock_urlopen, _sleep):
        """URLError should trigger exactly 3 attempts, then raise InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            _request("https://api.example.com/threads/1")

        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("inbox_tool.time.sleep", return_value=None)
    @patch("inbox_tool.urlopen")
    def test_httperror_is_not_retried(self, mock_urlopen, _sleep):
        """HTTPError should surface as InboxError on the first attempt."""
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

    @patch("inbox_tool.time.sleep", return_value=None)
    @patch("inbox_tool.urlopen")
    def test_transient_urlerror_recovers_on_retry(self, mock_urlopen, _sleep):
        """A successful retry after a URLError must not raise."""
        mock_urlopen.side_effect = [
            URLError("flaky network"),
            _make_response(b'{"thread": {"id": 1}}'),
        ]

        result = _request("https://api.example.com/threads/1")

        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertIsNotNone(result)

    @patch("inbox_tool.time.sleep", return_value=None)
    @patch("inbox_tool.urlopen")
    def test_successful_request_does_not_retry(self, mock_urlopen, _sleep):
        """A first-attempt success should call urlopen exactly once."""
        mock_urlopen.return_value = _make_response(b'{"thread": {}}')

        _request("https://api.example.com/threads/1")

        self.assertEqual(mock_urlopen.call_count, 1)


# --------------------------------------------------------------------------- #
# get_imessage_thread() — chat_id type flexibility
# --------------------------------------------------------------------------- #
class TestGetIMessageThread(unittest.TestCase):
    """Verify get_imessage_thread() accepts both int and str chat_id."""

    @patch("inbox_tool.urlopen")
    def test_accepts_int_chat_id(self, mock_urlopen):
        """An integer chat_id must be accepted and used in the request."""
        mock_urlopen.return_value = _make_response(b'{"thread": {"id": 42}}')

        result = get_imessage_thread(42)

        self.assertIsNotNone(result)
        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertIn("42", _extract_url(mock_urlopen))

    @patch("inbox_tool.urlopen")
    def test_accepts_str_chat_id(self, mock_urlopen):
        """A string chat_id must be accepted and used in the request."""
        mock_urlopen.return_value = _make_response(b'{"thread": {"id": "42"}}')

        result = get_imessage_thread("42")

        self.assertIsNotNone(result)
        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertIn("42", _extract_url(mock_urlopen))

    @patch("inbox_tool.urlopen")
    def test_int_and_str_target_the_same_endpoint(self, mock_urlopen):
        """Equivalent int and str chat_ids must produce equivalent URLs."""
        mock_urlopen.return_value = _make_response()
        get_imessage_thread(555)
        int_url = _extract_url(mock_urlopen)

        mock_urlopen.reset_mock()
        mock_urlopen.return_value = _make_response()
        get_imessage_thread("555")
        str_url = _extract_url(mock_urlopen)

        self.assertEqual(int_url, str_url)

    @patch("inbox_tool.urlopen")
    def test_underlying_request_propagates_urlerror_as_inbox_error(
        self, mock_urlopen
    ):
        """Errors from _request should surface as InboxError to callers."""
        mock_urlopen.side_effect = URLError("network down")

        with self.assertRaises(InboxError):
            get_imessage_thread(7)

        # Even though get_imessage_thread is one call, _request retries 3x.
        self.assertEqual(mock_urlopen.call_count, 3)


if __name__ == "__main__":
    unittest.main()
