# ---- New import needed at the top of src/harness.py ----
# Add `send_imessage` (and any other send_* you dispatch) to the inbox_tool
# import block. The function below depends on it being in scope.
#
# from src.inbox_tool import (
#     get_calendar_upcoming,
#     get_gmail_unread,
#     get_imessage_contacts,
#     get_linkedin_dms,
#     send_imessage,          # <-- add this
# )

# ---- Append to the bottom of src/harness.py ----

# Map the string function name stored in approval_payload["fn"] back to the
# actual callable in inbox_tool. Extend this as new side-effecting actions
# are added (send_gmail, delete_*, create_*, etc.).
_INBOX_FUNCTIONS: dict[str, Callable] = {
    "get_imessage_contacts": get_imessage_contacts,
    "get_gmail_unread": get_gmail_unread,
    "get_linkedin_dms": get_linkedin_dms,
    "get_calendar_upcoming": get_calendar_upcoming,
    "send_imessage": send_imessage,
}


def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Gate side-effecting actions on explicit user approval.

    Behavior:
      * result.needs_approval is False  -> return result unchanged (no gate).
      * result.needs_approval is True and confirmed is False
          -> return result unchanged so the caller can render the approval UI
             from result.approval_payload and call this function again with
             confirmed=True once the user has signed off.
      * result.needs_approval is True and confirmed is True
          -> look up approval_payload["fn"] in _INBOX_FUNCTIONS, invoke it
             with the remaining payload keys as kwargs, and return the final
             HarnessResult.

    The approval payload contract (set by route() for send/create/delete):
        {
            "platform": "imessage",   # human-readable label
            "action":   "send",       # verb for display ("send", "create", ...)
            "to":       "mom",        # target (varies by action)
            "body":     "...",        # payload content
            "fn":       "send_imessage",  # callable name in inbox_tool
        }
    Any extra keys in the payload are forwarded as kwargs to the target
    function, so this gate works uniformly across platforms as long as route()
    records the right "fn" name.
    """
    # Fast path: read-only result, nothing was ever pending.
    if not result.needs_approval:
        return result

    # Pending action, awaiting explicit confirmation from the user.
    if not confirmed:
        return result

    payload = result.approval_payload
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Approval payload is missing the 'fn' key; cannot execute.",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    fn = _INBOX_FUNCTIONS.get(fn_name)
    if fn is None:
        return HarnessResult(
            content=f"Unknown function '{fn_name}' in approval payload; refusing to execute.",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    # Treat every key in the payload except the dispatch key "fn" as a kwarg
    # to the target callable. This keeps the gate agnostic to the specifics
    # of each platform/action (to/body for messages, title/when for calendar,
    # path/contents for code, etc.).
    kwargs = {k: v for k, v in payload.items() if k != "fn"}

    try:
        output = fn(**kwargs)
    except TypeError as exc:
        # Most likely a kwarg mismatch between what route() recorded and
        # what the function actually accepts. Surface the contract error.
        return HarnessResult(
            content=(
                f"Approval payload keys {sorted(kwargs)} are not compatible "
                f"with {fn_name}: {exc}"
            ),
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure to the caller
        return HarnessResult(
            content=f"Execution of {fn_name} failed: {exc}",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    return HarnessResult(
        content=str(output),
        action_taken=payload.get("action", fn_name),
        needs_approval=False,
        approval_payload={},
    )
