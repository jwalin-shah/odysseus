# List of harness action names that require user approval before execution.
# These are "write" actions that modify state or send data externally.
_WRITE_ACTIONS = [
    "send",
    "calendar_create",
    "calendar_update",
    "calendar_delete",
    "email_send",
    "email_reply",
    "file_write",
    "file_delete",
    "file_move",
    "shell_exec",
    "http_post",
    "http_put",
    "http_delete",
    "db_write",
    "db_update",
    "db_delete",
    "deploy",
    "payment_send",
    "message_post",
    "task_complete",
]


def list_write_actions() -> list:
    """Return the canonical list of harness action names requiring user approval.

    Returns:
        list: A list of strings representing action names that mutate state
        or perform side effects and therefore must be approved by the user
        before execution.
    """
    return list(_WRITE_ACTIONS)
