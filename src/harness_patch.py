def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged so the
    caller can show an approval UI. If confirmed=True, look up the pending
    action function in src.inbox_tool by name and execute it, returning a
    final HarnessResult with the outcome.

    Expected approval_payload shape:
        {"platform": "imessage",
         "action":   "send",
         "to":       "mom",
         "body":     "...",
         "fn":       "send_imessage"}
    The 'fn' key names the callable; all other keys (except the metadata
    keys 'fn', 'platform', 'action') are forwarded as keyword arguments.
    """
    # No approval was required in the first place -> nothing to gate.
    if not result.needs_approval:
        return result
    # Caller hasn't confirmed yet -> hand the pending result back as-is.
    if not confirmed:
        return result

    payload = result.approval_payload
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Error: approval_payload is missing the 'fn' key.",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    # Dynamic lookup: pull the action function out of src.inbox_tool by name.
    import src.inbox_tool as inbox_tool
    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Error: function '{fn_name}' not found in src.inbox_tool.",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    # Build kwargs from the payload, stripping the metadata keys.
    _METADATA_KEYS = {"fn", "platform", "action"}
    kwargs = {k: v for k, v in payload.items() if k not in _METADATA_KEYS}

    try:
        exec_result = fn(**kwargs)
    except Exception as e:  # surface execution errors as a final result, not a crash
        return HarnessResult(
            content=f"Error executing {fn_name}: {e}",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    return HarnessResult(
        content=str(exec_result),
        action_taken=payload.get("action", "executed"),
        needs_approval=False,
        approval_payload={},
    )
