import pytest
from unittest.mock import patch
from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


# Fake shape that inbox_tool.fetch_all would return.
SAMPLE_INBOX = {
    "gmail": [
        {"id": "1", "unread": True},
        {"id": "2", "unread": False},
        {"id": "3", "unread": True},
    ],
    "slack": [
        {"id": "a", "unread": True},
        {"id": "b", "unread": True},
    ],
    "outlook": [],
}


@patch("src.workflow_engine.inbox_tool")
def test_inbox_summary_flow_returns_platform_unread_counts(mock_inbox):
    mock_inbox.fetch_all.return_value = SAMPLE_INBOX

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert set(result.keys()) == {"gmail", "slack", "outlook"}
    assert result["gmail"] == 2
    assert result["slack"] == 2
    assert result["outlook"] == 0
    mock_inbox.fetch_all.assert_called_once()


@patch("src.workflow_engine.inbox_tool")
def test_reply_flow_raises_before_sending(mock_inbox):
    with pytest.raises(ApprovalRequired):
        reply_flow(
            message_id="m1",
            platform="gmail",
            body="Sounds good.",
            approved=False,
        )

    # Critical: nothing was actually dispatched.
    mock_inbox.send_reply.assert_not_called()
    mock_inbox.send.assert_not_called()


@patch("src.workflow_engine.calendar_tool")
def test_calendar_add_flow_raises_before_creating_event(mock_calendar):
    with pytest.raises(ApprovalRequired):
        calendar_add_flow(
            title="Team standup",
            start="2025-01-01T09:00:00",
            end="2025-01-01T09:15:00",
            attendees=["a@example.com"],
            approved=False,
        )

    mock_calendar.create_event.assert_not_called()
