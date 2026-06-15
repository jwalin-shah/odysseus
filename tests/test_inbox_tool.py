"""Unit tests for src.inbox_tool."""

import json
from unittest import TestCase
from unittest.mock import patch, MagicMock

from urllib.error import URLError, HTTPError

from src.inbox_tool import _request, get_imessage_thread, InboxError


class RequestRetryTests(TestCase):
    """Tests for the retry behavior of _request()."""

    @patch("src.inbox_tool.urlopen")
    def test_urllib_error_retries_three_times(self, mock_urlopen):
        """URLError should be retried 3 times, then raise InboxError."""
        mock_urlopen.side_effect = URLError("connection failed")

        with self.assertRaises(InboxError):
            _request("GET", "http://example.com/api")

        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("src.inbox_tool.urlopen")
    def test_urllib_error_then_success(self, mock_urlopen):
        """A transient URLError followed by success should not raise."""
        success_response = MagicMock()
        success_response.read.return_value = json.dumps({"ok": True}).encode("utf-8")
        success_response.getcode.return_value = 200

        mock_urlopen.side_effect = [
            URLError("transient"),
            URLError("transient"),
            success_response,
        ]

        result = _request("GET", "http://example.com/api")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("src.inbox_tool.urlopen")
    def test_http_error_raises_immediately(self, mock_urlopen):
        """HTTPError should not trigger retries."""
        mock_urlopen.side_effect = HTTPError(
            "http://example.com/api", 500, "Server Error", {}, None
        )

        with self.assertRaises(InboxError):
            _request("GET", "http://example.com/api")

        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("src.inbox_tool.urlopen")
    def test_successful_request_returns_parsed_json(self, mock_urlopen):
        """A 200 response should return the parsed JSON body."""
        payload = {"threads": [{"id": 1, "text": "hi"}]}
        ok_response = MagicMock()
        ok_response.read.return_value = json.dumps(payload).encode("utf-8")
        ok_response.getcode.return_value = 200
        mock_urlopen.return_value = ok_response

        result = _request("GET", "http://example.com/api")

        self.assertEqual(result, payload)


class GetIMessageThreadTests(TestCase):
    """Tests for the get_imessage_thread() chat_id handling."""

    @patch("src.inbox_tool._request")
    def test_accepts_int_chat_id(self, mock_request):
        """get_imessage_thread should accept an integer chat_id."""
        mock_request.return_value = {"id": 42, "messages": []}

        result = get_imessage_thread(42)

        mock_request.assert_called_once()
        self.assertEqual(result, {"id": 42, "messages": []})

    @patch("src.inbox_tool._request")
    def test_accepts_str_chat_id(self, mock_request):
        """get_imessage_thread should accept a string chat_id."""
        mock_request.return_value = {"id": 42, "messages": []}

        result = get_imessage_thread("42")

        mock_request.assert_called_once()
        self.assertEqual(result, {"id": 42, "messages": []})

    @patch("src.inbox_tool._request")
    def test_int_and_str_produce_same_url(self, mock_request):
        """Both int and str chat_ids should resolve to the same endpoint."""
        mock_request.return_value = {}

        get_imessage_thread(7)
        url_from_int = mock_request.call_args[0][1]

        mock_request.reset_mock()
        mock_request.return_value = {}

        get_imessage_thread("7")
        url_from_str = mock_request.call_args[0][1]

        self.assertEqual(url_from_int, url_from_str)
