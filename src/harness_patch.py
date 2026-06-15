def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, execute the pending action and return the final result.

    The approval payload is expected to look like:
        {"platform": "imessage", "action": "send",
         "to": "mom", "body": "...", "fn": "send_imessage"}

    The value of ``fn`` is looked up by name on ``src.inbox_tool`` and invoked
    with the remaining payload fields passed as keyword arguments.
    """
    # No approval gate active — nothing to confirm/execute; return result as-is.
    if not result.needs_approval or not result.approval_payload:
        return result

    # Approval required but the user hasn't confirmed yet — the caller is
    # responsible for rendering the approval UI and re-invoking with confirmed=True.
    if not confirmed:
        return result

    # User approved — resolve the executor function from src.inbox_tool by name.
    from src import inbox_tool

    payload = result.approval_payload
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Approval payload is missing the 'fn' field; cannot execute.",
            action_taken="error",
        )

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Unknown action function '{fn_name}' in src.inbox_tool.",
            action_taken="error",
        )

    # Pass the remaining payload entries as kwargs. 'fn', 'action', and
    # 'platform' are dispatch/metadata fields, not function arguments.
    kwargs = {
        k: v for k, v in payload.items()
        if k not in ("fn", "action", "platform")
    }

    try:
        executed = fn(**kwargs)
    except Exception as e:
        return HarnessResult(
            content=f"Failed to execute '{fn_name}': {e}",
            action_taken="error",
        )

    return HarnessResult(
        content=executed if isinstance(executed, str) else str(executed),
        action_taken=payload.get("action", "execute"),
        needs_approval=False,
    )
