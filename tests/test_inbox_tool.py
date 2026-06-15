"""Unit tests for src/inbox_tool.py."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

# Add src directory to Python path so we can import inbox_tool
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"),
)

from inbox_tool import InboxError, _request, get_imessage_thread


class TestRequestRetryLogic(unittest.TestCase):
    """Test the retry logic in _request()."""

    @patch("inbox_tool.urlopen")
    @patch("inbox_tool.time.sleep", return_value=None)
    def test_urllib_error_retries_three_times(self, mock_sleep, mock_urlopen):
        """On URLError, _request() retries 3 times then raises InboxError."""
        # Configure the mock to always raise URLError on every call
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        # urlopen should be called exactly 3 times before giving up
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("inbox_tool.urlopen")
    @patch("inbox_tool.time.sleep", return_value=None)
    def test_http_error_no_retry(self, mock_sleep, mock_urlopen):
        """On HTTPError, _request() raises InboxError immediately (no retry)."""
        # Configure the mock to raise HTTPError.
        # Note: HTTPError is a subclass of URLError, so the source code must
        # check for HTTPError BEFORE URLError to avoid swallowing it.
        mock_urlopen.side_effect = HTTPError(
            url="http://example.com",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        # urlopen should only be called once - no retry on HTTPError
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("inbox_tool.urlopen")
    @patch("inbox_tool.time.sleep", return_value=None)
    def test_successful_response_does_not_retry(self, mock_sleep, mock_urlopen):
        """A successful response returns without retrying."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": true}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = _request("http://example.com/api")

        # Should be called exactly once (no retry needed on success)
        self.assertEqual(mock_urlopen.call_count, 1)
        # Sleep should not be called on a successful first attempt
        mock_sleep.assert_not_called()


class TestGetImessageThread(unittest.TestCase):
    """Test that get_imessage_thread() accepts both int and str chat_id."""

    def _make_mock_response(self, body=b'{"messages": []}'):
        """Build a context-manager-friendly mock HTTP response."""
        mock_response = MagicMock()
        mock_response.read.return_value = body
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        return mock_response

    @patch("inbox_tool.urlopen")
    def test_accepts_int_chat_id(self, mock_urlopen):
        """get_imessage_thread() accepts an integer chat_id without error."""
        mock_urlopen.return_value = self._make_mock_response()

        # Should not raise
        result = get_imessage_thread(12345)

        self.assertIsNotNone(result)
        mock_urlopen.assert_called_once()
        # The int chat_id should appear in the request URL
        called_url = mock_urlopen.call_args[0][0]
        self.assertIn("12345", called_url)

    @patch("inbox_tool.urlopen")
    def test_accepts_str_chat_id(self, mock_urlopen):
        """get_imessage_thread() accepts a string chat_id without error."""
        mock_urlopen.return_value = self._make_mock_response()

        # Should not raise
        result = get_imessage_thread("12345")

        self.assertIsNotNone(result)
        mock_urlopen.assert_called_once()
        # The str chat_id should appear in the request URL
        called_url = mock_urlopen.call_args[0][0]
        self.assertIn("12345", called_url)

    @patch("inbox_tool.urlopen")
    def test_int_and_str_chat_id_produce_same_url(self, mock_urlopen):
        """An int chat_id and the equivalent str chat_id yield the same URL."""
        mock_urlopen.return_value = self._make_mock_response()

        get_imessage_thread(12345)
        url_with_int = mock_urlopen.call_args[0][0]

        get_imessage_thread("12345")
        url_with_str = mock_urlopen.call_args[0][0]

        self.assertEqual(url_with_int, url_with_str)


if __name__ == "__main__":
    unittest.main()
