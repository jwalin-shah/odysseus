"""Unit tests for src/inbox_tool.py."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

# Make the src/ directory importable
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from inbox_tool import InboxError, _request, get_imessage_thread


def _make_mock_response(body: bytes = b'{"ok": true}'):
    """Build a mock that quacks like a urllib response object."""
    response = MagicMock()
    response.read.return_value = body
    return response


class TestRequestRetryLogic(unittest.TestCase):
    """Retry behaviour for the internal _request() helper."""

    @patch("time.sleep", return_value=None)
    @patch("urllib.request.urlopen")
    def test_urlerror_retries_three_times_then_raises(self, mock_urlopen, _sleep):
        """URLError: urlopen is called 3 times, then InboxError is raised."""
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("time.sleep", return_value=None)
    @patch("urllib.request.urlopen")
    def test_httperror_raises_immediately(self, mock_urlopen, _sleep):
        """HTTPError: InboxError is raised on the first failure with no retry."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.com/api",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        self.assertEqual(mock_urlopen.call_count, 1)


class TestGetIMessageThread(unittest.TestCase):
    """get_imessage_thread() should accept chat_id as int or str."""

    @patch("urllib.request.urlopen")
    def test_accepts_integer_chat_id(self, mock_urlopen):
        """Integer chat_id does not raise and triggers a single request."""
        mock_urlopen.return_value = _make_mock_response(b'{"messages": []}')

        result = get_imessage_thread(12345)

        mock_urlopen.assert_called_once()
        self.assertIsNotNone(result)

    @patch("urllib.request.urlopen")
    def test_accepts_string_chat_id(self, mock_urlopen):
        """String chat_id does not raise and triggers a single request."""
        mock_urlopen.return_value = _make_mock_response(b'{"messages": []}')

        result = get_imessage_thread("12345")

        mock_urlopen.assert_called_once()
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
