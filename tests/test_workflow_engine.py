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
    """inbox_summary_flow returns a dict keyed by platform with unread counts."""
    mock_inbox.fetch_summary.return_value = {
        "gmail": 7,
        "slack": 4,
        "teams": 2,
    }

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert set(result.keys()) == {"gmail", "slack", "teams"}
    assert result["gmail"] == 7
    assert result["slack"] == 4
    assert result["teams"] == 2
    mock_inbox.fetch_summary.assert_called_once()


@patch("src.workflow_engine.calendar_tool")
@patch("src.workflow_engine.messaging_tool")
@patch("src.workflow_engine.inbox_tool")
def test_reply_flow_raises_approval_required_before_sending(
    mock_inbox, mock_messaging, mock_calendar
):
    """reply_flow must raise ApprovalRequired before any send is executed."""
    with pytest.raises(ApprovalRequired):
        reply_flow(message_id="msg_001", body="Sounds good!")

    mock_messaging.send.assert_not_called()
    mock_calendar.create_event.assert_not_called()
    mock_inbox.send.assert_not_called()


@patch("src.workflow_engine.calendar_tool")
@patch("src.workflow_engine.messaging_tool")
@patch("src.workflow_engine.inbox_tool")
def test_calendar_add_flow_raises_approval_required_before_creating(
    mock_inbox, mock_messaging, mock_calendar
):
    """calendar_add_flow must raise ApprovalRequired before any event is created."""
    with pytest.raises(ApprovalRequired):
        calendar_add_flow(
            title="Team Sync",
            start="2024-01-15T10:00:00",
            duration_minutes=30,
        )

    mock_calendar.create_event.assert_not_called()
    mock_messaging.send.assert_not_called()
    mock_inbox.create_event.assert_not_called()
