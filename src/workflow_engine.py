"""Deterministic, approval-gated inbox workflows."""

from src import inbox_tool


class ApprovalRequired(Exception):
    def __init__(self, action: str, payload: dict):
        super().__init__(f"Approval required for {action}")
        self.action = action
        self.payload = payload


def inbox_summary_flow() -> dict[str, int]:
    platforms = ("gmail", "slack", "outlook")
    summary: dict[str, int] = {}
    for platform in platforms:
        count = inbox_tool.get_unread_count(platform)
        if count is None:
            raise ValueError(
                f"get_unread_count returned None for platform: {platform!r}"
            )
        summary[platform] = int(count)
    return summary


def reply_flow(platform: str, message_id: str, body: str) -> None:
    raise ApprovalRequired(
        "send_reply",
        {"platform": platform, "message_id": message_id, "body": body},
    )


def calendar_add_flow(
    title: str,
    start: str,
    end: str,
    attendees: list[str] | None = None,
) -> None:
    raise ApprovalRequired(
        "create_calendar_event",
        {
            "title": title,
            "start": start,
            "end": end,
            "attendees": attendees or [],
        },
    )
