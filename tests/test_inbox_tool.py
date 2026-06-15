"""Unit tests for src/inbox_tool.py.

Covers the retry behavior of _request() and the chat_id type
flexibility of get_imessage_thread().
"""
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

from src.inbox_tool import _request, get_imessage_thread, InboxError


class TestRequestRetryLogic(unittest.TestCase):
    """Test the retry behavior of the internal _request() helper."""

    @patch("time.sleep", return_value=None)
    @patch("urllib.request.urlopen")
    def test_retries_three_times_on_url_error(self, mock_urlopen, mock_sleep):
        """On URLError, _request should attempt 3 times then raise InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")
        test_url = "http://example.com/api/endpoint"

        with self.assertRaises(InboxError):
            _request(test_url)

        # Three total attempts (1 initial + 2 retries) before giving up.
        self.assertEqual(mock_urlopen.call_count, 3)

        # Every retry must hit the same URL.
        for call_args in mock_urlopen.call_args_list:
            self.assertEqual(call_args.args[0], test_url)

        # There should be sleep calls between retries (2 sleeps for 3 attempts).
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep", return_value=None)
    @patch("urllib.request.urlopen")
    def test_raises_inbox_error_immediately_on_http_error(
        self, mock_urlopen, mock_sleep
    ):
        """On HTTPError, _request should raise InboxError immediately (no retry)."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.com/api",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        # HTTPError is non-transient: only one attempt, no retries.
        self.assertEqual(mock_urlopen.call_count, 1)
        # Confirm we never slept (i.e. never retried).
        self.assertEqual(mock_sleep.call_count, 0)

    @patch("time.sleep", return_value=None)
    @patch("urllib.request.urlopen")
    def test_returns_response_on_success(self, mock_urlopen, mock_sleep):
        """On success, _request should return the urlopen response without retrying."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": true}'
        mock_urlopen.return_value = mock_response

        result = _request("http://example.com/api")

        self.assertIs(result, mock_response)
        self.assertEqual(mock_urlopen.call_count, 1)


class TestGetImessageThread(unittest.TestCase):
    """Test that get_imessage_thread() accepts both int and str chat_id values."""

    def _build_mock_response(self):
        """Construct a MagicMock that quacks like a urlopen response."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"messages": []}'
        return mock_response

    @patch("src.inbox_tool._request")
    def test_accepts_int_chat_id(self, mock_request):
        """An integer chat_id should be accepted and forwarded to _request."""
        mock_request.return_value = self._build_mock_response()

        # Must not raise any TypeError or validation error.
        get_imessage_thread(12345)

        mock_request.assert_called_once()
        # The int chat_id should appear in the URL/request passed down.
        self.assertIn("12345", str(mock_request.call_args))

    @patch("src.inbox_tool._request")
    def test_accepts_str_chat_id(self, mock_request):
        """A string chat_id should be accepted and forwarded to _request."""
        mock_request.return_value = self._build_mock_response()

        # Must not raise any TypeError or validation error.
        get_imessage_thread("chat_abc_123")

        mock_request.assert_called_once()
        # The str chat_id should appear in the URL/request passed down.
        self.assertIn("chat_abc_123", str(mock_request.call_args))

    @patch("src.inbox_tool._request")
    def test_int_and_str_produce_equivalent_request(self, mock_request):
        """An int chat_id and its str form should produce equivalent requests."""
        mock_request.return_value = self._build_mock_response()

        get_imessage_thread(99)
        int_call = str(mock_request.call_args)

        mock_request.reset_mock()
        mock_request.return_value = self._build_mock_response()

        get_imessage_thread("99")
        str_call = str(mock_request.call_args)

        # The chat_id value should appear in both calls regardless of type.
        self.assertIn("99", int_call)
        self.assertIn("99", str_call)


if __name__ == "__main__":
    unittest.main()
