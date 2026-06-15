import inspect
import src.inbox_tool as _inbox_tool

# Metadata keys stored in approval_payload that aren't function arguments.
_APPROVAL_META_KEYS = {"fn", "platform", "action"}


def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, execute the pending action and return the final result."""
    # Nothing pending, or user hasn't confirmed yet — just hand the result back.
    if not result.needs_approval or not confirmed:
        return result

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Approval payload missing 'fn'.",
            action_taken="approval_error",
            needs_approval=False,
            approval_payload={},
        )

    # Look up the executable by name in inbox_tool.
    fn = getattr(_inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Unknown action function: {fn_name}",
            action_taken="approval_error",
            needs_approval=False,
            approval_payload={},
        )

    # Only forward keys the target function actually accepts, and skip metadata.
    try:
        valid_params = set(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        valid_params = set()
    kwargs = {
        k: v
        for k, v in payload.items()
        if k in valid_params and k not in _APPROVAL_META_KEYS
    }

    try:
        fn(**kwargs)
    except Exception as e:
        return HarnessResult(
            content=f"Action '{payload.get('action')}' failed: {e}",
            action_taken="execution_error",
            needs_approval=False,
            approval_payload={},
        )

    return HarnessResult(
        content=(
            f"Action '{payload.get('action')}' on {payload.get('platform')} completed."
        ),
        action_taken=payload.get("action", "unknown"),
        needs_approval=False,
        approval_payload={},
    )
