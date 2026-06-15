"""Unit tests for src/workflow_engine.py"""
import pytest
from unittest.mock import patch, MagicMock

from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


@patch("src.workflow_engine.inbox_tool")
def test_inbox_summary_flow_returns_platform_unread_counts(mock_inbox):
    mock_inbox.fetch_gmail.return_value = [
        {"id": "1", "unread": True},
        {"id": "2", "unread": False},
    ]
    mock_inbox.fetch_slack.return_value = [
        {"id": "a", "unread": True},
        {"id": "b", "unread": True},
    ]
    mock_inbox.fetch_outlook.return_value = []

    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert set(result.keys()) == {"gmail", "slack", "outlook"}
    assert result["gmail"] == 1
    assert result["slack"] == 2
    assert result["outlook"] == 0
    mock_inbox.fetch_gmail.assert_called_once()
    mock_inbox.fetch_slack.assert_called_once()
    mock_inbox.fetch_outlook.assert_called_once()


@patch("src.workflow_engine.inbox_tool")
def test_reply_flow_requires_approval_before_send(mock_inbox):
    mock_inbox.send_reply = MagicMock()

    with pytest.raises(ApprovalRequired):
        reply_flow(message_id="m1", body="looks good")

    mock_inbox.send_reply.assert_not_called()


@patch("src.workflow_engine.inbox_tool")
def test_calendar_add_flow_requires_approval_before_create(mock_inbox):
    mock_inbox.create_event = MagicMock()

    with pytest.raises(ApprovalRequired):
        calendar_add_flow(
            title="Standup",
            start="2025-01-01T10:00:00Z",
            duration_min=30,
        )

    mock_inbox.create_event.assert_not_called()


@patch("src.workflow_engine.inbox_tool")
def test_approval_required_message_mentions_action(mock_inbox):
    mock_inbox.send_reply = MagicMock()
    with pytest.raises(ApprovalRequired) as exc:
        reply_flow(message_id="m2", body="hi")
    assert "send" in str(exc.value).lower() or "reply" in str(exc.value).lower()
