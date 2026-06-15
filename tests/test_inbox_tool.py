import unittest
from unittest.mock import patch
from urllib.error import URLError, HTTPError
import sys
import os

# Add src directory to Python path so we can import inbox_tool
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from inbox_tool import _request, get_imessage_thread, InboxError


class TestRequestRetryLogic(unittest.TestCase):
    """Test the retry logic in _request()."""

    @patch('urllib.request.urlopen')
    def test_urlerror_retries_3_times_then_raises(self, mock_urlopen):
        """On URLError, _request should retry 3 times then raise InboxError."""
        # Configure the mock to always raise URLError
        mock_urlopen.side_effect = URLError("connection refused")

        # Expect InboxError after exhausting retries
        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        # Verify urlopen was called exactly 3 times
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch('urllib.request.urlopen')
    def test_httperror_raises_immediately(self, mock_urlopen):
        """On HTTPError, _request should raise InboxError immediately (no retry)."""
        # Configure the mock to raise HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="http://example.com/api",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        # Expect InboxError to be raised
        with self.assertRaises(InboxError):
            _request("http://example.com/api")

        # Verify urlopen was called exactly once (no retry on HTTPError)
        self.assertEqual(mock_urlopen.call_count, 1)


class TestGetIMessageThread(unittest.TestCase):
    """Test that get_imessage_thread accepts both int and str chat_id."""

    @patch('inbox_tool._request')
    def test_accepts_int_chat_id(self, mock_request):
        """get_imessage_thread should accept an integer chat_id."""
        mock_request.return_value = {"messages": []}

        # Should not raise TypeError when given an int
        get_imessage_thread(12345)

        # Verify _request was called once with the int chat_id
        mock_request.assert_called_once()
        call_args, call_kwargs = mock_request.call_args
        self.assertTrue(
            12345 in call_args or 12345 in call_kwargs.values(),
            "Expected int chat_id 12345 to be passed to _request",
        )

    @patch('inbox_tool._request')
    def test_accepts_str_chat_id(self, mock_request):
        """get_imessage_thread should accept a string chat_id."""
        mock_request.return_value = {"messages": []}

        # Should not raise TypeError when given a str
        get_imessage_thread("12345")

        # Verify _request was called once with the str chat_id
        mock_request.assert_called_once()
        call_args, call_kwargs = mock_request.call_args
        self.assertTrue(
            "12345" in call_args or "12345" in call_kwargs.values(),
            "Expected str chat_id '12345' to be passed to _request",
        )


if __name__ == "__main__":
    unittest.main()
