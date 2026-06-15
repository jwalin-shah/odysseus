import pytest
from unittest.mock import patch

from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


@patch("src.workflow_engine.inbox_tool")
def test_inbox_summary_flow_returns_platforms_and_counts(mock_inbox):
    mock_inbox.fetch.return_value = [
        {"platform": "gmail", "unread": 3},
        {"platform": "slack", "unread": 5},
        {"platform": "gmail", "unread": 2},
        {"platform": "outlook", "unread": 0},
    ]

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert set(result.keys()) == {"gmail", "slack", "outlook"}
    assert result["gmail"] == 5
    assert result["slack"] == 5
    assert result["outlook"] == 0
    mock_inbox.fetch.assert_called_once()


@patch("src.workflow_engine.inbox_tool")
def test_reply_flow_raises_before_sending(mock_inbox):
    with pytest.raises(ApprovalRequired):
        reply_flow(message_id="msg_123", body="Sounds good.")

    mock_inbox.send.assert_not_called()


@patch("src.workflow_engine.calendar_tool")
@patch("src.workflow_engine.inbox_tool")
def test_calendar_add_flow_raises_before_creating_event(mock_inbox, mock_calendar):
    with pytest.raises(ApprovalRequired):
        calendar_add_flow(
            title="Team Standup",
            start="2024-06-01T10:00:00",
            duration_minutes=30,
            attendees=["alice@example.com"],
        )

    mock_calendar.create_event.assert_not_called()
