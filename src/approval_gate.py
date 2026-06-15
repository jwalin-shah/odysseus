"""Approval gate for classifying harness tool actions as read or write."""


_WRITE_INDICATORS = (
    "write",
    "send",
    "create",
    "update",
    "delete",
    "modify",
    "post",
    "put",
    "patch",
    "remove",
    "append",
    "insert",
    "set",
    "save",
    "upload",
    "publish",
)

_READ_INDICATORS = (
    "read",
    "get",
    "fetch",
    "list",
    "view",
    "query",
    "search",
    "find",
    "describe",
    "inspect",
)


def classify_write_action(tool_name: str) -> bool:
    """Return True if the named harness tool performs a state-mutating write action.

    Classification is performed by inspecting the tool name for action-oriented
    keywords. A tool is considered a write action when it contains a write
    indicator and is not exclusively a read indicator. Unknown tool names default
    to a non-write (safer) classification.
    """
    lowered = tool_name.lower()

    has_write = any(token in lowered for token in _WRITE_INDICATORS)
    has_read = any(token in lowered for token in _READ_INDICATORS)

    if has_read and not has_write:
        return False

    return has_write
