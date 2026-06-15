# Add this import alongside the existing inbox_tool imports at the top of harness.py:
import src.inbox_tool as inbox_tool


# Append at the bottom of src/harness.py:

def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Gate a write action on explicit user confirmation.

    - If result.needs_approval is False: return result unchanged (no gate).
    - If result.needs_approval is True and confirmed is False: return result
      unchanged so the caller can render an approval UI.
    - If result.needs_approval is True and confirmed is True: look up the
      pending function by name in src.inbox_tool (via approval_payload["fn"]),
      call it with the remaining payload keys as kwargs, and return the
      final HarnessResult.

    Expected approval_payload shape (built by route()):
        {"platform": "imessage", "action": "send",
         "to": "mom", "body": "...", "fn": "send_imessage"}
    The "fn" key is consumed here; everything else is forwarded as kwargs.
    """
    # No gate required: nothing to confirm.
    if not result.needs_approval:
        return result

    # Gate required but user has not yet confirmed: hand back to the caller
    # so it can display the approval UI with the pending payload.
    if not confirmed:
        return result

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")

    if not fn_name:
        return HarnessResult(
            content="Approval received, but no action function was specified.",
            action_taken="error",
            needs_approval=False,
        )

    # Resolve the action handler by name from the inbox_tool module.
    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Unknown action function: {fn_name!r}",
            action_taken="error",
            needs_approval=False,
        )

    # Forward every payload key except "fn" as a kwarg to the resolved function.
    kwargs = {k: v for k, v in payload.items() if k != "fn"}

    try:
        output = fn(**kwargs)
    except TypeError as e:
        # Most likely a kwarg mismatch between payload and function signature.
        return HarnessResult(
            content=f"Bad arguments for {fn_name}: {e}",
            action_taken="error",
            needs_approval=False,
        )
    except Exception as e:
        return HarnessResult(
            content=f"Failed to execute {fn_name}: {e}",
            action_taken="error",
            needs_approval=False,
        )

    return HarnessResult(
        content=str(output) if output is not None else f"{fn_name} completed.",
        action_taken=fn_name,
        needs_approval=False,
    )
