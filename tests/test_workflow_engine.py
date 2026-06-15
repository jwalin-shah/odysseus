import pytest
from unittest.mock import patch
from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


def test_inbox_summary_flow_returns_platform_counts():
    """inbox_summary_flow returns a dict keyed by platform with unread counts."""
    fake_counts = {"gmail": 5, "slack": 3, "teams": 2}
    with patch("src.workflow_engine.inbox_tool") as mock_inbox:
        mock_inbox.get_unread_counts.return_value = fake_counts
        result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert set(result.keys()) == {"gmail", "slack", "teams"}
    assert result == fake_counts
    assert all(isinstance(v, int) for v in result.values())


def test_reply_flow_raises_approval_required_before_send():
    """reply_flow raises ApprovalRequired and never reaches inbox_tool.send_reply."""
    with patch("src.workflow_engine.inbox_tool") as mock_inbox:
        with pytest.raises(ApprovalRequired):
            reply_flow(message_id="msg-1", body="Acknowledged.")

    mock_inbox.send_reply.assert_not_called()


def test_calendar_add_flow_raises_approval_required_before_create():
    """calendar_add_flow raises ApprovalRequired and never creates an event."""
    with patch("src.workflow_engine.calendar_tool") as mock_cal:
        with pytest.raises(ApprovalRequired):
            calendar_add_flow(
                title="Standup",
                start="2024-01-01T10:00:00",
                end="2024-01-01T10:30:00",
                attendees=["alice@example.com"],
            )

    mock_cal.create_event.assert_not_called()
