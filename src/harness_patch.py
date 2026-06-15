def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Gate an action that returned needs_approval=True.

    - If result.needs_approval is False, pass it through unchanged.
    - If result.needs_approval is True and confirmed is False, return it
      unchanged so the caller can render the approval UI to the user.
    - If result.needs_approval is True and confirmed is True, look up the
      function named in approval_payload['fn'] on src.inbox_tool, invoke
      it with the remaining payload fields as keyword arguments, and
      attach the return value to the result.

    Expected approval_payload shape (built by route()):
        {
            "platform": "imessage",
            "action":   "send",
            "to":       "mom",
            "body":     "...",
            "fn":       "send_imessage",   # function on src.inbox_tool
        }
    Any keys besides "fn" are forwarded as kwargs to the resolved function.
    """
    # Nothing pending — pass through.
    if not result.needs_approval:
        return result

    # Caller hasn't approved yet — let them show the approval UI.
    if not confirmed:
        return result

    payload = dict(result.approval_payload)
    fn_name = payload.pop("fn", None)
    if not fn_name:
        result.content = (
            f"Approval payload missing 'fn' field: {result.approval_payload!r}"
        )
        result.action_taken = "error:missing_fn"
        result.needs_approval = False
        return result

    # Resolve the function by name on src.inbox_tool. Done locally so this
    # patch doesn't require adding a new top-level import.
    import src.inbox_tool as inbox_tool
    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        result.content = f"Unknown or non-callable function on inbox_tool: {fn_name}"
        result.action_taken = f"error:unknown_fn:{fn_name}"
        result.needs_approval = False
        return result

    # Execute the pending action. Anything other than 'fn' in the payload
    # is treated as a kwarg for the target function.
    try:
        output = fn(**payload)
    except TypeError as e:
        # Most likely a kwargs/arity mismatch — surface it cleanly.
        result.content = f"Bad arguments for {fn_name}: {e}"
        result.action_taken = f"error:bad_args:{fn_name}"
        result.needs_approval = False
        return result
    except Exception as e:
        result.content = f"Execution of {fn_name} failed: {e}"
        result.action_taken = f"error:exec:{fn_name}"
        result.needs_approval = False
        return result

    result.content = "" if output is None else str(output)
    result.action_taken = f"executed:{fn_name}"
    # Approval is satisfied — drop the gate so downstream handlers don't
    # re-prompt.
    result.needs_approval = False
    return result
