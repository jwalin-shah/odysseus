import pytest
from unittest.mock import patch, MagicMock

from src.workflow_engine import (
    inbox_summary_flow,
    reply_flow,
    calendar_add_flow,
    ApprovalRequired,
)


@pytest.fixture
def mock_inbox_tool():
    """Provide a mock inbox_tool with sensible unread counts."""
    with patch("src.workflow_engine.inbox_tool") as mock:
        mock.get_unread_count.side_effect = lambda platform: {
            "email": 5,
            "slack": 3,
            "twitter": 2,
        }.get(platform, 0)
        yield mock


def test_inbox_summary_flow_returns_platform_keys_and_counts(mock_inbox_tool):
    result = inbox_summary_flow()

    assert isinstance(result, dict)
    assert set(result.keys()) == {"email", "slack", "twitter"}
    assert result == {"email": 5, "slack": 3, "twitter": 2}
    assert mock_inbox_tool.get_unread_count.call_count == 3


def test_inbox_summary_flow_calls_expected_platforms(mock_inbox_tool):
    inbox_summary_flow()

    called_platforms = {
        call.args[0] for call in mock_inbox_tool.get_unread_count.call_args_list
    }
    assert called_platforms == {"email", "slack", "twitter"}


def test_reply_flow_raises_approval_required_before_sending(mock_inbox_tool):
    with pytest.raises(ApprovalRequired):
        reply_flow(
            platform="email",
            message_id="msg_123",
            reply_text="Sounds good!",
        )

    # Ensure no send action was performed
    mock_inbox_tool.send.assert_not_called()
    mock_inbox_tool.send_message.assert_not_called()


def test_reply_flow_approval_contains_message_context(mock_inbox_tool):
    with pytest.raises(ApprovalRequired) as exc_info:
        reply_flow(
            platform="slack",
            message_id="msg_456",
            reply_text="Approved",
        )

    # The exception should carry enough context for a human reviewer
    assert "msg_456" in str(exc_info.value)
    assert exc_info.value.requires_human_approval is True


def test_calendar_add_flow_raises_approval_required_before_creation(mock_inbox_tool):
    event = {
        "title": "Team standup",
        "start": "2026-02-01T10:00:00",
        "end": "2026-02-01T10:30:00",
    }

    with pytest.raises(ApprovalRequired):
        calendar_add_flow(event)

    # No calendar mutation should have occurred
    mock_inbox_tool.create_event.assert_not_called()
    mock_inbox_tool.calendar_add.assert_not_called()


def test_calendar_add_flow_does_not_partial_mutate_on_approval_failure(mock_inbox_tool):
    event = {"title": "Roadmap review", "start": "2026-02-02T14:00:00"}

    with pytest.raises(ApprovalRequired):
        calendar_add_flow(event)

    # No inbox_tool method that mutates state should have been touched
    for attr in ("send", "send_message", "create_event", "calendar_add", "delete_event"):
        getattr(mock_inbox_tool, attr).assert_not_called()
