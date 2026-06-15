import src.inbox_tool as inbox_tool


# Metadata keys inside approval_payload that describe routing, not function args.
_PAYLOAD_META = {"platform", "action", "fn"}


def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Gate a HarnessResult behind explicit user approval.

    - If result.needs_approval is True and confirmed is False, return result
      unchanged so the caller can render the approval UI.
    - If result.needs_approval is True and confirmed is True, look up the
      pending function by name in src.inbox_tool, call it with the remaining
      approval_payload fields as kwargs, and return a fresh HarnessResult
      describing the execution outcome.
    - If result.needs_approval is False, return result unchanged.
    """
    # Hold: caller hasn't confirmed yet, surface the pending request as-is.
    if result.needs_approval and not confirmed:
        return result

    # Nothing pending; result is already the final answer.
    if not result.needs_approval:
        return result

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")

    if not fn_name:
        return HarnessResult(
            content="Approval confirmed but approval_payload is missing 'fn'.",
            action_taken="error",
            needs_approval=False,
        )

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Approval confirmed but '{fn_name}' is not an exported "
                    f"callable on src.inbox_tool.",
            action_taken="error",
            needs_approval=False,
        )

    # Everything that isn't a routing key becomes a kwarg to the tool.
    kwargs = {k: v for k, v in payload.items() if k not in _PAYLOAD_META}

    try:
        out = fn(**kwargs)
    except TypeError as e:
        # Wrong kwargs for the resolved function — fail loud so the caller can
        # surface a useful diagnostic instead of silently doing nothing.
        return HarnessResult(
            content=f"Refused to call {fn_name}({kwargs!r}): {e}",
            action_taken="error",
            needs_approval=False,
        )
    except Exception as e:
        return HarnessResult(
            content=f"Execution of {fn_name} failed: {e}",
            action_taken="error",
            needs_approval=False,
        )

    action_label = f"{payload.get('platform', 'unknown')}.{payload.get('action', 'unknown')}"
    return HarnessResult(
        content=out if isinstance(out, str) else str(out),
        action_taken=action_label,
        needs_approval=False,
        approval_payload={},
    )
