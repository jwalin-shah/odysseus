"""Unit tests for src.inbox_tool.

Covers:
  * The retry policy of the private _request() helper.
  * chat_id type tolerance (int vs str) on get_imessage_thread().

All network I/O is mocked via unittest.mock.patch on urllib.request.urlopen.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from urllib.error import HTTPError, URLError

from src.inbox_tool import InboxError, _request, get_imessage_thread


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mock_response(payload):
    """Build a context-manager-friendly MagicMock that returns *payload* JSON."""
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def _captured_url(mock_request):
    """Return the URL string passed to a patched _request, regardless of style."""
    args, kwargs = mock_request.call_args
    if "url" in kwargs:
        return kwargs["url"]
    if args:
        return str(args[0])
    raise AssertionError("No URL captured on _request call")


# ---------------------------------------------------------------------------
# _request() — retry semantics
# ---------------------------------------------------------------------------

class TestRequestRetryLogic:
    @patch("urllib.request.urlopen")
    def test_urlerror_is_retried_exactly_three_times(self, mock_urlopen):
        """A URLError that never recovers must be retried 3x and then wrapped in InboxError."""
        mock_urlopen.side_effect = URLError("connection refused")

        with pytest.raises(InboxError):
            _request("https://api.example.com/inbox")

        assert mock_urlopen.call_count == 3, (
            "URLError should trigger exactly 3 attempts before giving up"
        )

    @patch("urllib.request.urlopen")
    def test_urlerror_eventually_succeeds(self, mock_urlopen):
        """Two URLErrors followed by a successful response should return the payload."""
        mock_urlopen.side_effect = [
            URLError("blip 1"),
            URLError("blip 2"),
            _mock_response({"ok": True}),
        ]

        result = _request("https://api.example.com/inbox")

        assert result == {"ok": True}
        assert mock_urlopen.call_count == 3

    @patch("urllib.request.urlopen")
    def test_httperror_is_not_retried(self, mock_urlopen):
        """An HTTPError (4xx/5xx) is a server response, not a transport blip — no retry."""
        mock_urlopen.side_effect = HTTPError(
            url="https://api.example.com/inbox",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )

        with pytest.raises(InboxError):
            _request("https://api.example.com/inbox")

        assert mock_urlopen.call_count == 1, (
            "HTTPError must surface as InboxError on the first attempt only"
        )

    @patch("urllib.request.urlopen")
    def test_success_on_first_try_calls_urlopen_once(self, mock_urlopen):
        """Sanity check: a clean first response is returned without extra attempts."""
        mock_urlopen.return_value = _mock_response({"hello": "world"})

        result = _request("https://api.example.com/inbox")

        assert result == {"hello": "world"}
        assert mock_urlopen.call_count == 1


# ---------------------------------------------------------------------------
# get_imessage_thread() — chat_id type handling
# ---------------------------------------------------------------------------

class TestGetImessageThreadChatId:
    @patch("src.inbox_tool._request")
    def test_accepts_int_chat_id(self, mock_request):
        """An integer chat_id must be accepted without TypeError."""
        mock_request.return_value = {"messages": []}

        result = get_imessage_thread(12345)

        assert result == {"messages": []}
        mock_request.assert_called_once()
        assert "12345" in _captured_url(mock_request)

    @patch("src.inbox_tool._request")
    def test_accepts_str_chat_id(self, mock_request):
        """A string chat_id must be accepted unchanged."""
        mock_request.return_value = {"messages": []}

        result = get_imessage_thread("chat-abc")

        assert result == {"messages": []}
        mock_request.assert_called_once()
        assert "chat-abc" in _captured_url(mock_request)

    @patch("src.inbox_tool._request")
    def test_int_and_str_collapse_to_same_endpoint(self, mock_request):
        """12345 and '12345' should hit the same URL — int must be coerced to str."""
        mock_request.return_value = {}

        get_imessage_thread(12345)
        url_from_int = _captured_url(mock_request)

        mock_request.reset_mock()
        get_imessage_thread("12345")
        url_from_str = _captured_url(mock_request)

        assert url_from_int == url_from_str, (
            f"int and str chat_ids produced different URLs: {url_from_int!r} vs {url_from_str!r}"
        )

    @patch("src.inbox_tool._request")
    def test_inbox_error_propagates_from_request(self, mock_request):
        """If _request raises InboxError, get_imessage_thread should let it bubble up."""
        mock_request.side_effect = InboxError("upstream failed")

        with pytest.raises(InboxError, match="upstream failed"):
            get_imessage_thread(42)
