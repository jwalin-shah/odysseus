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
    mock_inbox_tool.fetch_unread.side_effect = {
        "gmail": 5,
        "slack": 3,
        "teams": 2,
    }.__getitem__

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert result == {"gmail": 5, "slack": 3, "teams": 2}
    platforms_called = {
        call.args[0] for call in mock_inbox_tool.fetch_unread.call_args_list
    }
    assert platforms_called == {"gmail", "slack", "teams"}


@patch("src.workflow_engine.inbox_tool")
def test_reply_flow_raises_approval_required_before_sending(mock_inbox_tool):
    with pytest.raises(ApprovalRequired):
        reply_flow(message_id="msg-1", body="Sounds good!")

    mock_inbox_tool.send.assert_not_called()


@patch("src.workflow_engine.inbox_tool")
def test_calendar_add_flow_raises_approval_required_before_creating(mock_inbox_tool):
    with pytest.raises(ApprovalRequired):
        calendar_add_flow(
            title="Standup",
            start="2025-01-01T10:00:00",
            duration_minutes=30,
        )

    mock_inbox_tool.create_event.assert_not_called()
