"""Unit tests for src/workflow_engine.py."""
import pytest
from unittest.mock import patch, MagicMock

from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


# ---------------------------------------------------------------------------
# 1. inbox_summary_flow
# ---------------------------------------------------------------------------
@patch("src.workflow_engine.inbox_tool")
def test_inbox_summary_flow_returns_platform_unread_counts(mock_inbox_tool):
    """Should return a dict mapping platform -> unread count."""
    mock_inbox_tool.get_inbox_summary.return_value = {
        "gmail": 5,
        "slack": 3,
        "discord": 2,
    }

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert result == {"gmail": 5, "slack": 3, "discord": 2}
    assert all(isinstance(v, int) for v in result.values())
    mock_inbox_tool.get_inbox_summary.assert_called_once()


@patch("src.workflow_engine.inbox_tool")
def test_inbox_summary_flow_empty_inbox(mock_inbox_tool):
    """Empty inbox should still return a dict (possibly empty)."""
    mock_inbox_tool.get_inbox_summary.return_value = {}

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert result == {}
    mock_inbox_tool.get_inbox_summary.assert_called_once()


# ---------------------------------------------------------------------------
# 2. reply_flow
# ---------------------------------------------------------------------------
@patch("src.workflow_engine.inbox_tool")
def test_reply_flow_raises_approval_required_before_sending(mock_inbox_tool):
    """reply_flow must surface ApprovalRequired and never call send_reply."""
    mock_inbox_tool.get_message.return_value = {
        "id": "msg_123",
        "platform": "gmail",
        "from": "alice@example.com",
        "subject": "Hello",
        "body": "Original body",
    }

    with pytest.raises(ApprovalRequired):
        reply_flow("msg_123", "Thanks, will check and revert!")

    # Critical: nothing should have been sent out
    mock_inbox_tool.send_reply.assert_not_called()


# ---------------------------------------------------------------------------
# 3. calendar_add_flow
# ---------------------------------------------------------------------------
@patch("src.workflow_engine.inbox_tool")
def test_calendar_add_flow_raises_approval_required_before_creating(
    mock_inbox_tool,
):
    """calendar_add_flow must surface ApprovalRequired before create_event."""
    event_payload = {
        "title": "Team Sync",
        "start": "2026-02-01T10:00:00Z",
        "end": "2026-02-01T10:30:00Z",
        "attendees": ["bob@example.com"],
    }

    with pytest.raises(ApprovalRequired):
        calendar_add_flow(event_payload)

    # Critical: no event should be created until approval is granted
    mock_inbox_tool.create_event.assert_not_called()
