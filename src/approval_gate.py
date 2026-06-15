def format_confirmation_prompt(action_summary: str, risk: str) -> str:
    """Render a CLI prompt asking the user to approve, edit, or abort a write action.

    The risk tier is highlighted visually so the operator can spot dangerous
    actions at a glance. ANSI colour codes are used when the terminal is
    likely to be interactive; the literal tier name (e.g. ``HIGH RISK``) is
    also embedded so plain text consumers and tests can find it.
    """
    risk_normalized = (risk or "").strip().lower() or "unknown"
    if risk_normalized == "high":
        risk_display = "\033[1;41;97m  HIGH RISK  \033[0m"
    elif risk_normalized == "medium":
        risk_display = "\033[1;43;30m  MEDIUM RISK  \033[0m"
    elif risk_normalized == "low":
        risk_display = "\033[1;42;30m  LOW RISK  \033[0m"
    else:
        risk_display = f"  {risk_normalized.upper()} RISK  "

    border = "-" * max(48, len(action_summary) + 16)
    lines = [
        "Pending write action",
        border,
        f"  Action : {action_summary}",
        f"  Risk   : {risk_display}",
        border,
        "",
        "Approve, edit, or abort this action? [y/n] ",
    ]
    return "\n".join(lines)


_APPROVE_RESPONSES = frozenset({
    "y", "yes", "yeah", "yep", "yup", "ya",
    "ok", "okay", "k",
    "sure", "alright", "allright",
    "true", "t",
    "1",
    "approve", "approved", "accept", "accepted",
    "go", "proceed", "continue", "do it", "doit",
    "yessir", "yeppers", "aye", "affirmative", "roger",
    "yeah sure", "yes please",
})

_DENY_RESPONSES = frozenset({
    "n", "no", "nope", "nah", "na", "nay",
    "false", "f",
    "0",
    "deny", "denied", "reject", "rejected", "refuse", "refused",
    "stop", "cancel", "abort", "halt",
    "negative", "no way", "nuh-uh", "no thanks",
})


def parse_confirmation(raw: str) -> str:
    """Normalize a free-form CLI confirmation response.

    Returns 'approve' for yes-like inputs (y/yes/ok/sure/...), 'deny' for
    no-like inputs (n/no/nope/stop/...), and 'unknown' for anything that
    isn't a clear yes or no (including empty/whitespace, punctuation only,
    or ambiguous words like 'maybe').
    """
    if raw is None:
        return "unknown"
    text = str(raw).strip().lower()
    if not text:
        return "unknown"
    # Strip trailing punctuation/symbols ("yes!", "y.", "n?", "no,", ...)
    # but keep the word content intact so multi-word answers like
    # "yes please" or "no thanks" still match.
    normalized = "".join(ch for ch in text if not ch in ".,!?;:'\"")
    normalized = " ".join(normalized.split())
    if not normalized:
        return "unknown"
    if normalized in _APPROVE_RESPONSES:
        return "approve"
    if normalized in _DENY_RESPONSES:
        return "deny"
    return "unknown"


assert parse_confirmation('y') == 'approve'
assert parse_confirmation('N') == 'deny'
assert parse_confirmation('maybe') == 'unknown'
