"""Unit tests for src/inbox_tool.py.

Covers:
  * _request() retry semantics on URLError vs HTTPError
  * get_imessage_thread() accepting both int and str chat_id
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

# Make `src/inbox_tool.py` importable regardless of where pytest is invoked from.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from inbox_tool import _request, get_imessage_thread, InboxError  # noqa: E402


def _http_error(code: int = 500) -> HTTPError:
    """Helper to build an HTTPError for mocking."""
    return HTTPError(
        url="http://localhost/api",
        code=code,
        msg="Server Error",
        hdrs={},
        fp=None,
    )


class TestRequestRetryLogic(unittest.TestCase):
    """Tests for the retry behaviour of _request()."""

    @patch("inbox_tool.urlopen")
    def test_urlerror_retries_three_times_then_raises(self, mock_urlopen):
        """On URLError, _request retries 3 times, then raises InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            _request("http://localhost/api")

        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("inbox_tool.urlopen")
    def test_httperror_raises_immediately_no_retry(self, mock_urlopen):
        """On HTTPError, _request raises InboxError on the first failure (no retry)."""
        mock_urlopen.side_effect = _http_error(500)

        with self.assertRaises(InboxError):
            _request("http://localhost/api")

        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("inbox_tool.urlopen")
    def test_httperror_raises_inbox_error_not_httperror(self, mock_urlopen):
        """HTTPError must be translated to InboxError, not propagated raw."""
        mock_urlopen.side_effect = _http_error(404)

        # If _request() leaked HTTPError, this assertRaises would fail.
        with self.assertRaises(InboxError):
            _request("http://localhost/api")

    @patch("inbox_tool.urlopen")
    def test_successful_request_does_not_retry(self, mock_urlopen):
        """A successful response should be returned on the first attempt with no retries."""
        response = MagicMock()
        response.read.return_value = b'{"ok": true}'
        mock_urlopen.return_value = response

        result = _request("http://localhost/api")

        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertIs(result, response)

    @patch("inbox_tool.urlopen")
    def test_recovery_after_transient_urlerror(self, mock_urlopen):
        """If a transient URLError is followed by success, _request should return the response."""
        response = MagicMock()
        response.read.return_value = b'{"ok": true}'
        # Fail once, then succeed.
        mock_urlopen.side_effect = [URLError("blip"), response]

        result = _request("http://localhost/api")

        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertIs(result, response)


class TestGetImessageThreadChatId(unittest.TestCase):
    """Tests for get_imessage_thread() chat_id type handling."""

    def setUp(self):
        # Each test patches _request; provide a benign return value.
        self._mock_response = MagicMock()
        self._mock_response.read.return_value = b'{"messages": []}'

    @patch("inbox_tool._request")
    def test_accepts_int_chat_id(self, mock_request):
        mock_request.return_value = self._mock_response

        # Must not raise TypeError.
        result = get_imessage_thread(12345)

        mock_request.assert_called_once()
        # The chat_id should appear in the URL/arguments.
        self.assertIn("12345", str(mock_request.call_args))

    @patch("inbox_tool._request")
    def test_accepts_str_chat_id(self, mock_request):
        mock_request.return_value = self._mock_response

        # Must not raise TypeError.
        result = get_imessage_thread("12345")

        mock_request.assert_called_once()
        self.assertIn("12345", str(mock_request.call_args))

    @patch("inbox_tool._request")
    def test_int_and_str_chat_ids_produce_identical_request(self, mock_request):
        """Passing 12345 (int) and '12345' (str) should produce the same underlying request."""
        mock_request.return_value = self._mock_response

        get_imessage_thread(12345)
        int_call = mock_request.call_args

        mock_request.reset_mock()
        mock_request.return_value = self._mock_response
        get_imessage_thread("12345")
        str_call = mock_request.call_args

        # Same URL, same params — only the chat_id type differed at the call site.
        self.assertEqual(int_call, str_call)

    @patch("inbox_tool._request")
    def test_propagates_inbox_error_from_request(self, mock_request):
        """If _request raises InboxError, get_imessage_thread should propagate it."""
        mock_request.side_effect = InboxError("upstream failure")

        with self.assertRaises(InboxError):
            get_imessage_thread(12345)


if __name__ == "__main__":
    unittest.main()
