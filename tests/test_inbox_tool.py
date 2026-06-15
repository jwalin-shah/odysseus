"""Unit tests for src.inbox_tool."""
import json
import pytest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError

from src.inbox_tool import _request, get_imessage_thread, InboxError


def _make_urlopen_response(body):
    """Build a mock urlopen response that yields a JSON body."""
    response = MagicMock()
    response.read.return_value = json.dumps(body).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def _called_url(mock_urlopen):
    """Extract the URL string from the most recent urlopen call."""
    args, kwargs = mock_urlopen.call_args
    target = args[0] if args else kwargs.get("url")
    if hasattr(target, "full_url"):
        return target.full_url
    return str(target)


class TestRequestRetry:
    """Tests for the retry behaviour of _request()."""

    @patch("src.inbox_tool.urlopen")
    def test_retries_three_times_on_urlerror(self, mock_urlopen):
        """URLError should trigger 3 attempts before raising InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")

        with pytest.raises(InboxError):
            _request("http://example.com/api")

        assert mock_urlopen.call_count == 3

    @patch("src.inbox_tool.urlopen")
    def test_does_not_retry_on_http_error(self, mock_urlopen):
        """HTTPError should raise InboxError immediately, no retries."""
        mock_urlopen.side_effect = HTTPError(
            url="http://example.com/api",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with pytest.raises(InboxError):
            _request("http://example.com/api")

        assert mock_urlopen.call_count == 1

    @patch("src.inbox_tool.urlopen")
    def test_succeeds_after_transient_urlerror(self, mock_urlopen):
        """A successful response on a later attempt should be returned."""
        success = _make_urlopen_response({"ok": True})
        mock_urlopen.side_effect = [URLError("transient"), success]

        result = _request("http://example.com/api")

        assert result == {"ok": True}
        assert mock_urlopen.call_count == 2

    @patch("src.inbox_tool.urlopen")
    def test_succeeds_on_first_attempt(self, mock_urlopen):
        """A clean first attempt should not trigger any retries."""
        mock_urlopen.return_value = _make_urlopen_response({"ok": True})

        result = _request("http://example.com/api")

        assert result == {"ok": True}
        assert mock_urlopen.call_count == 1


class TestGetImessageThread:
    """Tests for the chat_id type handling in get_imessage_thread()."""

    @patch("src.inbox_tool.urlopen")
    def test_accepts_int_chat_id(self, mock_urlopen):
        """get_imessage_thread should accept an integer chat_id."""
        mock_urlopen.return_value = _make_urlopen_response(
            {"chat_id": 12345, "messages": []}
        )

        result = get_imessage_thread(12345)

        assert result == {"chat_id": 12345, "messages": []}
        assert "12345" in _called_url(mock_urlopen)

    @patch("src.inbox_tool.urlopen")
    def test_accepts_str_chat_id(self, mock_urlopen):
        """get_imessage_thread should accept a string chat_id."""
        mock_urlopen.return_value = _make_urlopen_response(
            {"chat_id": "12345", "messages": []}
        )

        result = get_imessage_thread("12345")

        assert result == {"chat_id": "12345", "messages": []}
        assert "12345" in _called_url(mock_urlopen)

    @patch("src.inbox_tool.urlopen")
    def test_int_and_str_produce_equivalent_urls(self, mock_urlopen):
        """int and str chat_ids should resolve to the same underlying request."""
        mock_urlopen.return_value = _make_urlopen_response({"messages": []})

        get_imessage_thread(42)
        url_with_int = _called_url(mock_urlopen)

        get_imessage_thread("42")
        url_with_str = _called_url(mock_urlopen)

        assert url_with_int == url_with_str
        assert mock_urlopen.call_count == 2
