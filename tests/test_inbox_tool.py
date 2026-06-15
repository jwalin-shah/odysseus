"""Unit tests for src.inbox_tool.py.

Covers:
- Retry logic in _request() on URLError (retries 3 times, then raises InboxError).
- Failure handling in _request() on HTTPError (raises InboxError immediately).
- get_imessage_thread() accepting both int and str chat_id values.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

from src.inbox_tool import _request, get_imessage_thread, InboxError


def make_http_error(code=500, msg="Server Error"):
    """Helper to build an HTTPError instance for use as a mock side_effect."""
    return HTTPError(
        url="http://example.com/api",
        code=code,
        msg=msg,
        hdrs={},
        fp=None,
    )


def make_url_error():
    """Helper to build a URLError instance for use as a mock side_effect."""
    return URLError("connection failed")


def make_mock_response(payload=None):
    """Helper to build a mock urlopen response object with a JSON payload."""
    if payload is None:
        payload = {"ok": True}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestRequestRetryLogic(unittest.TestCase):
    """Tests for the retry behavior of _request()."""

    @patch("src.inbox_tool.urlopen")
    def test_urlerror_retries_three_times_then_raises(self, mock_urlopen):
        """On URLError, _request retries up to 3 times then raises InboxError."""
        mock_urlopen.side_effect = make_url_error()

        with self.assertRaises(InboxError):
            _request("http://example.com/api/thread/12345")

        # Must have attempted exactly 3 times before giving up.
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("src.inbox_tool.urlopen")
    def test_urlerror_succeeds_on_third_attempt(self, mock_urlopen):
        """If a transient URLError clears up, _request returns the response."""
        mock_urlopen.side_effect = [
            make_url_error(),
            make_url_error(),
            make_mock_response({"messages": []}),
        ]

        result = _request("http://example.com/api/thread/12345")

        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(result, {"messages": []})

    @patch("src.inbox_tool.urlopen")
    def test_urlerror_succeeds_on_first_attempt(self, mock_urlopen):
        """If urlopen succeeds on the first try, no retries are made."""
        mock_urlopen.return_value = make_mock_response({"ok": True})

        result = _request("http://example.com/api/thread/12345")

        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertEqual(result, {"ok": True})

    @patch("src.inbox_tool.urlopen")
    def test_httperror_raises_immediately(self, mock_urlopen):
        """On HTTPError, _request raises InboxError without any retries."""
        mock_urlopen.side_effect = make_http_error(code=500, msg="Server Error")

        with self.assertRaises(InboxError):
            _request("http://example.com/api/thread/12345")

        # No retries should occur for HTTPError.
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("src.inbox_tool.urlopen")
    def test_httperror_raises_immediately_for_4xx(self, mock_urlopen):
        """On a 4xx HTTPError, _request raises InboxError without retrying."""
        mock_urlopen.side_effect = make_http_error(code=404, msg="Not Found")

        with self.assertRaises(InboxError):
            _request("http://example.com/api/thread/12345")

        self.assertEqual(mock_urlopen.call_count, 1)


class TestGetIMessageThreadChatId(unittest.TestCase):
    """Tests for get_imessage_thread()'s chat_id parameter handling."""

    @patch("src.inbox_tool._request")
    def test_accepts_int_chat_id(self, mock_request):
        """get_imessage_thread should accept an int chat_id without error."""
        mock_request.return_value = {"messages": []}

        # Should not raise a TypeError or similar.
        result = get_imessage_thread(12345)

        mock_request.assert_called_once()
        self.assertEqual(result, {"messages": []})

    @patch("src.inbox_tool._request")
    def test_accepts_str_chat_id(self, mock_request):
        """get_imessage_thread should accept a str chat_id without error."""
        mock_request.return_value = {"messages": []}

        # Should not raise a TypeError or similar.
        result = get_imessage_thread("12345")

        mock_request.assert_called_once()
        self.assertEqual(result, {"messages": []})

    @patch("src.inbox_tool._request")
    def test_int_and_str_chat_id_produce_equivalent_requests(self, mock_request):
        """int and str chat_id values should yield the same downstream request."""
        mock_request.return_value = {"messages": []}

        get_imessage_thread(12345)
        int_call_args = mock_request.call_args

        mock_request.reset_mock()

        get_imessage_thread("12345")
        str_call_args = mock_request.call_args

        self.assertEqual(int_call_args, str_call_args)

    @patch("src.inbox_tool._request")
    def test_chat_id_is_passed_through(self, mock_request):
        """The chat_id argument should be passed through to _request verbatim."""
        mock_request.return_value = {"messages": []}

        get_imessage_thread(67890)

        # The chat_id should appear in the call args (URL or kwargs) of _request.
        all_args = str(mock_request.call_args)
        self.assertIn("67890", all_args)


if __name__ == "__main__":
    unittest.main()
