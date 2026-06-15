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
    counts = {"gmail": 5, "slack": 3, "outlook": 0}
    mock_inbox_tool.get_unread_count.side_effect = lambda platform: counts[platform]

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert result == counts
    assert set(result.keys()) == {"gmail", "slack", "outlook"}
    assert all(isinstance(v, int) for v in result.values())
    assert mock_inbox_tool.get_unread_count.call_count == len(counts)


@patch("src.workflow_engine.inbox_tool")
def test_reply_flow_raises_approval_required_before_sending(mock_inbox_tool):
    with pytest.raises(ApprovalRequired):
        reply_flow(
            platform="gmail",
            message_id="msg_123",
            body="Thanks, will do!",
        )

    mock_inbox_tool.send.assert_not_called()
    mock_inbox_tool.send_message.assert_not_called()


@patch("src.workflow_engine.inbox_tool")
def test_calendar_add_flow_raises_approval_required_before_creating(mock_inbox_tool):
    with pytest.raises(ApprovalRequired):
        calendar_add_flow(
            title="Team Standup",
            start="2024-01-15T10:00:00",
            end="2024-01-15T10:30:00",
            attendees=["alice@example.com"],
        )

    mock_inbox_tool.create_event.assert_not_called()
