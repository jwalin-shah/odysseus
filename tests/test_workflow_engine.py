"""Unit tests for src.workflow_engine — uses pytest + unittest.mock.patch."""
import pytest
from unittest.mock import patch
from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


def test_inbox_summary_flow_returns_platform_keys_and_unread_counts():
    """Summary should be a dict keyed by platform with integer unread counts."""
    slack_messages = [
        {"id": "s1", "unread": True},
        {"id": "s2", "unread": False},
        {"id": "s3", "unread": True},
    ]
    email_messages = [
        {"id": "e1", "unread": True},
        {"id": "e2", "unread": False},
    ]

    with patch("src.workflow_engine.fetch_slack_inbox", return_value=slack_messages), \
         patch("src.workflow_engine.fetch_email_inbox", return_value=email_messages):
        result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert set(result.keys()) == {"slack", "email"}
    assert result["slack"] == 2
    assert result["email"] == 1


def test_reply_flow_raises_approval_required_before_sending():
    """reply_flow must halt on ApprovalRequired and never invoke send_reply."""
    with patch("src.workflow_engine.send_reply") as mock_send:
        with pytest.raises(ApprovalRequired):
            reply_flow(message_id="msg_001", body="Looks good, thanks!")
        mock_send.assert_not_called()


def test_calendar_add_flow_raises_approval_required_before_creating():
    """calendar_add_flow must halt on ApprovalRequired and never create events."""
    event = {"title": "Sprint Planning", "start": "2026-02-01T09:00:00Z"}
    with patch("src.workflow_engine.create_calendar_event") as mock_create:
        with pytest.raises(ApprovalRequired):
            calendar_add_flow(event=event)
        mock_create.assert_not_called()
