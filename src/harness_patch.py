def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, execute the pending action and return the final result."""
    # Nothing pending — no gating required.
    if not result.needs_approval:
        return result
    # Approval not yet given — let the caller surface the prompt.
    if not confirmed:
        return result

    from src import inbox_tool

    fn_name = result.approval_payload.get("fn")
    if not fn_name:
        result.content = "Approval payload is missing the 'fn' key; cannot execute."
        result.needs_approval = False
        result.action_taken = "approval_error:missing_fn"
        return result

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None:
        result.content = f"Function '{fn_name}' not found in src.inbox_tool."
        result.needs_approval = False
        result.action_taken = f"approval_error:unknown_fn:{fn_name}"
        return result

    # All payload keys except 'fn' are forwarded as kwargs to the resolved callable.
    kwargs = {k: v for k, v in result.approval_payload.items() if k != "fn"}
    try:
        output = fn(**kwargs)
    except TypeError as e:
        # Most likely a kwarg name mismatch — surface it loudly.
        result.content = f"Argument mismatch calling {fn_name}({kwargs}): {e}"
        result.needs_approval = False
        result.action_taken = f"approval_error:bad_args:{fn_name}"
        return result
    except Exception as e:
        result.content = f"Execution of {fn_name} failed: {e}"
        result.needs_approval = False
        result.action_taken = f"approval_error:exception:{fn_name}"
        return result

    # Success — promote the result out of the approval-pending state.
    result.content = str(output) if output is not None else f"Action '{fn_name}' completed."
    result.needs_approval = False
    result.action_taken = f"executed:{fn_name}"
    return result
