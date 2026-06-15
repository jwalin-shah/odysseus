"""Unit tests for src.workflow_engine."""
from unittest.mock import patch, MagicMock

import pytest

from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


def test_inbox_summary_flow_returns_platform_keys_and_unread_counts():
    """Flow aggregates unread counts per platform into a dict."""
    with patch("src.workflow_engine.inbox_tool") as mock_inbox:
        mock_inbox.gmail.fetch_unread.return_value = 7
        mock_inbox.slack.fetch_unread.return_value = 2
        mock_inbox.outlook.fetch_unread.return_value = 0

        result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert set(result.keys()) >= {"gmail", "slack", "outlook"}
    assert result["gmail"] == 7
    assert result["slack"] == 2
    assert result["outlook"] == 0


def test_reply_flow_raises_approval_required_before_sending():
    """Reply flow must request human approval and never call send()."""
    mock_inbox = MagicMock()
    with patch("src.workflow_engine.inbox_tool", mock_inbox):
        with pytest.raises(ApprovalRequired):
            reply_flow(
                platform="gmail",
                message_id="msg_abc123",
                body="Sounds good, will take a look.",
            )

    mock_inbox.gmail.send.assert_not_called()
    mock_inbox.slack.send.assert_not_called()
    mock_inbox.outlook.send.assert_not_called()


def test_calendar_add_flow_raises_approval_required_before_creating_event():
    """Calendar flow must request human approval and never create an event."""
    mock_cal = MagicMock()
    with patch("src.workflow_engine.calendar_tool", mock_cal):
        with pytest.raises(ApprovalRequired):
            calendar_add_flow(
                title="Team Standup",
                start="2026-01-15T10:00:00",
                duration_min=30,
                attendees=["alice@example.com"],
            )

    mock_cal.create_event.assert_not_called()
    mock_cal.google.create_event.assert_not_called()
    mock_cal.add_event.assert_not_called()
