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
    mock_inbox.list_email.return_value = [
        {"id": "e1", "unread": True},
        {"id": "e2", "unread": True},
        {"id": "e3", "unread": False},
    ]
    mock_inbox.list_slack.return_value = [{"id": "s1", "unread": True}]
    mock_inbox.list_teams.return_value = []
    mock_inbox.list_sms.return_value = [{"id": "m1", "unread": True}]

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert result == {"email": 2, "slack": 1, "teams": 0, "sms": 1}
    mock_inbox.list_email.assert_called_once()
    mock_inbox.list_slack.assert_called_once()


@patch("src.workflow_engine.inbox_tool")
def test_reply_flow_raises_approval_required_before_sending(mock_inbox):
    with pytest.raises(ApprovalRequired):
        reply_flow(message_id="m1", body="Acknowledged", platform="email")
    mock_inbox.send_email.assert_not_called()
    mock_inbox.send_slack.assert_not_called()


@patch("src.workflow_engine.inbox_tool")
def test_calendar_add_flow_raises_approval_required_before_creating_event(mock_inbox):
    with pytest.raises(ApprovalRequired):
        calendar_add_flow(
            title="Standup",
            start="2024-01-01T10:00:00",
            duration_min=30,
            attendees=["alice@example.com"],
        )
    mock_inbox.create_event.assert_not_called()
