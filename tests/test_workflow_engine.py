import os
import sys
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


PLATFORMS = ("slack", "email", "teams")


@patch("workflow_engine.inbox_tool")
def test_inbox_summary_flow_returns_platform_counts(mock_inbox):
    mock_inbox.fetch_summary.side_effect = lambda platform, user_id: {
        "platform": platform,
        "unread": 5,
    }

    result = inbox_summary_flow(user_id="u1")

    assert isinstance(result, dict)
    for platform in PLATFORMS:
        assert platform in result
        assert result[platform]["unread"] == 5
    assert mock_inbox.fetch_summary.call_count == len(PLATFORMS)


@patch("workflow_engine.inbox_tool")
def test_reply_flow_requires_approval(mock_inbox):
    mock_inbox.send_message.return_value = {"sent": True}

    with pytest.raises(ApprovalRequired):
        reply_flow(message_id="m1", body="hello", user_id="u1")

    mock_inbox.send_message.assert_not_called()


@patch("workflow_engine.inbox_tool")
def test_calendar_add_flow_requires_approval(mock_inbox):
    mock_inbox.create_event.return_value = {"event_id": "e1"}

    with pytest.raises(ApprovalRequired):
        calendar_add_flow(
            title="Standup",
            start="2024-01-01T10:00:00Z",
            end="2024-01-01T10:30:00Z",
            user_id="u1",
        )

    mock_inbox.create_event.assert_not_called()
