def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Gate an approval-required result.

    - If result.needs_approval is False: pass through unchanged.
    - If result.needs_approval is True and confirmed is False: pass through unchanged
      so the caller can render an approval UI.
    - If confirmed is True: look up the function named in approval_payload["fn"]
      on src.inbox_tool, invoke it with the appropriate arguments from the payload,
      and return a new HarnessResult with the execution outcome.

    The approval_payload contract:
        {
            "platform": "imessage" | "gmail" | "calendar" | ...,
            "action":   "send" | "create" | "delete" | ...,
            "fn":       "<function name in src.inbox_tool>",
            ...function-specific args (e.g. to, body, message_id, title, ...)...
        }
    """
    # No approval gate on this result: pass through.
    if not result.needs_approval:
        return result

    # Approval gate present, but user has not confirmed: return unchanged so the
    # caller can surface the approval UI.
    if not confirmed:
        return result

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Approval payload is missing 'fn' (function name).",
            action_taken="error",
            needs_approval=False,
        )

    # Resolve the function by name on src.inbox_tool.
    from src import inbox_tool as _inbox_tool

    fn = getattr(_inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Function '{fn_name}' not found in src.inbox_tool.",
            action_taken="error",
            needs_approval=False,
        )

    # Pull the routing metadata out of the payload; everything else is forwarded
    # to the target function as kwargs (with a few named-arg overrides for
    # the well-known tool entry points so callers don't need to remember exact
    # keyword names).
    routing_keys = {"platform", "action", "fn"}
    extra = {k: v for k, v in payload.items() if k not in routing_keys}

    try:
        if fn_name == "send_imessage":
            output = fn(to=payload["to"], body=payload["body"])
        elif fn_name == "create_calendar_event":
            output = fn(
                title=payload.get("title", ""),
                start=payload.get("start", ""),
                end=payload.get("end", ""),
            )
        elif fn_name == "delete_gmail":
            output = fn(message_id=payload["message_id"])
        else:
            # Generic fallback: forward all non-routing payload keys as kwargs.
            output = fn(**extra)
    except KeyError as e:
        return HarnessResult(
            content=f"Missing required argument {e!s} for '{fn_name}'.",
            action_taken="error",
            needs_approval=False,
        )
    except Exception as e:
        return HarnessResult(
            content=f"Error executing '{fn_name}': {e}",
            action_taken="error",
            needs_approval=False,
        )

    return HarnessResult(
        content=str(output) if output is not None else "Done.",
        action_taken=f"executed:{fn_name}",
        needs_approval=False,
        approval_payload=payload,
    )
