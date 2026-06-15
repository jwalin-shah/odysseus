def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, execute the pending action and return the final result."""
    # No approval gate on this result — pass through untouched.
    if not result.needs_approval:
        return result
    # Approval required but not yet granted: caller is expected to render the
    # approval UI from result.approval_payload and call us again with confirmed=True.
    if not confirmed:
        return result

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Approval payload missing 'fn' — cannot execute.",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    # Resolve the executor by name against src.inbox_tool.
    from src import inbox_tool
    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Executor '{fn_name}' not found in inbox_tool.",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    # Forward everything in the payload as kwargs, minus the control fields
    # ('fn' selects the executor, 'action' is just a label for the UI/log).
    kwargs = {k: v for k, v in payload.items() if k not in ("fn", "action")}

    try:
        outcome = fn(**kwargs)
    except Exception as exc:  # noqa: BLE001 — surface the real error to the caller
        return HarnessResult(
            content=f"Failed to execute {fn_name}: {exc}",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    # Successful execution: produce a terminal HarnessResult (no further gating).
    return HarnessResult(
        content=f"Executed {fn_name}: {outcome}",
        action_taken=payload.get("action", fn_name),
        needs_approval=False,
        approval_payload={},
    )
