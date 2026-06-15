import pytest
from unittest.mock import patch
from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


@patch("src.workflow_engine.inbox_tool")
def test_inbox_summary_flow_returns_platform_unread_counts(mock_inbox):
    mock_inbox.fetch_gmail.return_value = [
        {"id": "1", "unread": True},
        {"id": "2", "unread": True},
        {"id": "3", "unread": False},
    ]
    mock_inbox.fetch_slack.return_value = [
        {"id": "10", "unread": True},
        {"id": "11", "unread": True},
        {"id": "12", "unread": True},
    ]

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert result.get("gmail") == 2
    assert result.get("slack") == 3
    mock_inbox.fetch_gmail.assert_called_once()
    mock_inbox.fetch_slack.assert_called_once()


@patch("src.workflow_engine.inbox_tool")
def test_reply_flow_raises_before_sending(mock_inbox):
    with pytest.raises(ApprovalRequired):
        reply_flow(
            platform="gmail",
            message_id="msg-42",
            body="Thanks for your help!",
        )

    mock_inbox.send_message.assert_not_called()


@patch("src.workflow_engine.inbox_tool")
def test_calendar_add_flow_raises_before_creating(mock_inbox):
    with pytest.raises(ApprovalRequired):
        calendar_add_flow(
            title="Team Standup",
            start="2026-02-01T10:00:00Z",
            duration_minutes=30,
            attendees=["alice@example.com"],
        )

    mock_inbox.create_event.assert_not_called()
