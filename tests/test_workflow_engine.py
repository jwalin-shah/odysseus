import pytest
from unittest.mock import patch

from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


@patch("src.workflow_engine.inbox_tool")
def test_inbox_summary_flow_returns_platform_unread_counts(mock_inbox_tool):
    """inbox_summary_flow should return a dict mapping platform -> unread count."""
    mock_inbox_tool.fetch_summary.return_value = {
        "gmail": 5,
        "slack": 3,
        "teams": 2,
    }

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert result == {"gmail": 5, "slack": 3, "teams": 2}
    assert all(isinstance(v, int) for v in result.values())
    mock_inbox_tool.fetch_summary.assert_called_once()


@patch("src.workflow_engine.inbox_tool")
def test_reply_flow_raises_approval_required_before_sending(mock_inbox_tool):
    """reply_flow must raise ApprovalRequired and never call send_reply."""
    with pytest.raises(ApprovalRequired):
        reply_flow(message_id="msg_123", body="Thanks for the update!")

    mock_inbox_tool.send_reply.assert_not_called()
    mock_inbox_tool.send_message.assert_not_called()


@patch("src.workflow_engine.inbox_tool")
def test_calendar_add_flow_raises_approval_required_before_creating(mock_inbox_tool):
    """calendar_add_flow must raise ApprovalRequired and never create an event."""
    event = {
        "title": "Team sync",
        "start": "2024-01-15T10:00:00",
        "duration_minutes": 30,
    }

    with pytest.raises(ApprovalRequired):
        calendar_add_flow(event=event)

    mock_inbox_tool.create_event.assert_not_called()
    mock_inbox_tool.create_calendar_event.assert_not_called()


@patch("src.workflow_engine.inbox_tool")
def test_approval_required_is_specific_exception(mock_inbox_tool):
    """ApprovalRequired should be a distinct, catchable exception class."""
    assert issubclass(ApprovalRequired, Exception)
    with pytest.raises(ApprovalRequired) as exc_info:
        reply_flow(message_id="m1", body="hi")
    assert "approval" in str(exc_info.value).lower()
