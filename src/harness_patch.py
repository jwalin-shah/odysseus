# Add to the existing import block at the top of src/harness.py:
#   import src.inbox_tool as inbox_tool
# (No per-function imports needed for the writers — we look them up by name.)


def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, look up result.approval_payload["fn"] on src.inbox_tool, call it with the
    remaining payload entries as kwargs, and return the final HarnessResult.

    Expected approval_payload shape (produced by route()):
        {
            "platform": "imessage" | "gmail" | "calendar" | ...,
            "action":   "send" | "create" | "delete" | ...,
            "fn":       "<inbox_tool function name>",   # e.g. "send_imessage"
            # ...action-specific kwargs, e.g. "to", "body", "subject", "start", "end"
        }
    """
    import src.inbox_tool as inbox_tool

    # Fast path: nothing was gated, or caller hasn't decided yet.
    if not result.needs_approval:
        return result
    if not confirmed:
        # Caller is responsible for rendering the approval UI from result.approval_payload.
        return result

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")
    if not isinstance(fn_name, str) or not fn_name:
        result.content = "Approval payload is missing 'fn' (function name)."
        result.action_taken = "error:no_fn"
        return result

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        result.content = f"Unknown inbox_tool function: {fn_name!r}"
        result.action_taken = f"error:unknown_fn:{fn_name}"
        return result

    # Forward every payload key except the routing metadata as kwargs to the writer.
    _METADATA_KEYS = ("fn", "action", "platform")
    kwargs = {k: v for k, v in payload.items() if k not in _METADATA_KEYS}

    try:
        output = fn(**kwargs)
    except TypeError as e:
        # Most common cause: payload key names don't match the function's parameter names.
        result.content = f"Bad arguments for {fn_name}: {e}"
        result.action_taken = f"error:bad_args:{fn_name}"
        return result
    except Exception as e:
        result.content = f"{fn_name} failed: {e}"
        result.action_taken = f"error:{fn_name}"
        return result

    # Success: close out the approval gate so the caller can serialize/finalize.
    result.content = str(output) if output is not None else f"Executed {fn_name}."
    result.action_taken = f"executed:{fn_name}"
    result.needs_approval = False
    return result
