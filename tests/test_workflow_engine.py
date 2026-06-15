"""Unit tests for src.workflow_engine flows.

Mocks inbox_tool (and calendar) calls to verify behavior in isolation.
"""

import pytest
from unittest.mock import patch

from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
)
from src.exceptions import ApprovalRequired


# ---- inbox_summary_flow --------------------------------------------------

@patch("src.workflow_engine.fetch_unread")
def test_inbox_summary_flow_returns_platform_unread_counts(mock_fetch):
    # Return a known unread count per platform
    fake_counts = {"gmail": 5, "slack": 3, "outlook": 7}
    mock_fetch.side_effect = lambda platform: fake_counts[platform]

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert set(result.keys()) == {"gmail", "slack", "outlook"}
    assert result == fake_counts
    assert mock_fetch.call_count == 3


# ---- reply_flow ----------------------------------------------------------

@patch("src.workflow_engine.send_reply")
def test_reply_flow_raises_approval_required_before_sending(mock_send):
    with pytest.raises(ApprovalRequired):
        reply_flow(
            message_id="msg_123",
            reply_text="Thanks, will review.",
        )

    # Critical: no reply should be sent without approval
    mock_send.assert_not_called()


# ---- calendar_add_flow ---------------------------------------------------

@patch("src.workflow_engine.create_event")
def test_calendar_add_flow_raises_approval_required_before_creating(mock_create):
    event = {
        "title": "Team Standup",
        "start": "2026-01-20T10:00:00Z",
        "end": "2026-01-20T10:30:00Z",
    }

    with pytest.raises(ApprovalRequired):
        calendar_add_flow(event)

    # Critical: no event should be created without approval
    mock_create.assert_not_called()
