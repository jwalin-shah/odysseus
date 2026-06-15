import pytest
from unittest.mock import patch

from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


@pytest.fixture
def sample_inbox_data():
    return {
        "gmail": [{"id": "1", "unread": True}, {"id": "2", "unread": False}],
        "slack": [{"id": "3", "unread": True}],
        "outlook": [],
    }


def test_inbox_summary_flow_returns_platform_counts(sample_inbox_data):
    with patch("src.workflow_engine.inbox_tool") as mock_tool:
        mock_tool.fetch_all_messages.return_value = sample_inbox_data
        result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert set(result.keys()) >= {"gmail", "slack", "outlook"}
    assert result["gmail"] == 1
    assert result["slack"] == 1
    assert result["outlook"] == 0
    mock_tool.fetch_all_messages.assert_called_once()


def test_reply_flow_raises_before_sending():
    with patch("src.workflow_engine.inbox_tool") as mock_tool:
        mock_tool.send_reply.return_value = {"status": "sent", "id": "msg-1"}

        with pytest.raises(ApprovalRequired):
            reply_flow(
                platform="gmail",
                message_id="1",
                body="Thanks, will check.",
            )

        mock_tool.send_reply.assert_not_called()


def test_calendar_add_flow_raises_before_creating_event():
    with patch("src.workflow_engine.inbox_tool") as mock_tool:
        mock_tool.create_calendar_event.return_value = {"event_id": "evt-1"}

        with pytest.raises(ApprovalRequired):
            calendar_add_flow(
                title="Sync with team",
                start="2026-02-01T10:00:00Z",
                duration_minutes=30,
            )

        mock_tool.create_calendar_event.assert_not_called()
