import pytest
from unittest.mock import patch
from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


@patch("src.workflow_engine.fetch_unread_counts")
def test_inbox_summary_flow_returns_platform_counts(mock_fetch):
    mock_fetch.return_value = {"gmail": 7, "slack": 4, "outlook": 2}
    result = inbox_summary_flow()
    assert isinstance(result, dict)
    assert "gmail" in result
    assert "slack" in result
    assert "outlook" in result
    assert result["gmail"] == 7
    assert result["slack"] == 4
    assert result["outlook"] == 2
    mock_fetch.assert_called_once()


@patch("src.workflow_engine.send_reply")
def test_reply_flow_requires_approval(mock_send):
    with pytest.raises(ApprovalRequired):
        reply_flow(message_id="msg_1", body="Hi there")
    mock_send.assert_not_called()


@patch("src.workflow_engine.create_event")
def test_calendar_add_flow_requires_approval(mock_create):
    event = {"title": "Standup", "start": "2024-06-01T10:00"}
    with pytest.raises(ApprovalRequired):
        calendar_add_flow(event)
    mock_create.assert_not_called()
