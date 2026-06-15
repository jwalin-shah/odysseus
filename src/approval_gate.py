def format_confirmation_prompt(action_name: str, action_args: dict) -> str:
    lines = [f"Approve {action_name}?"]
    for key, value in action_args.items():
        lines.append(f"  {key}: {value}")
    lines.append("[y/N] ")
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

_EDIT_RESPONSES = frozenset({
    "e", "edit",
    "edit please", "edit it",
    "modify", "modify please",
    "change", "change it",
    "revise", "update", "adjust", "fix", "correct",
    "tweak", "amend",
})


def parse_confirmation(answer: str) -> str:
    """Normalize a free-form CLI confirmation response.

    Returns one of 'approve', 'deny', or 'edit'. Empty/whitespace inputs
    and anything unrecognized default to 'deny'.
    """
    if answer is None:
        return "deny"
    text = str(answer).strip().lower()
    if not text:
        return "deny"
    # Strip trailing punctuation/symbols ("yes!", "y.", "n?", "no,", ...)
    # but keep the word content intact so multi-word answers like
    # "yes please" or "no thanks" still match.
    normalized = "".join(ch for ch in text if ch not in ".,!?;:'\"")
    normalized = " ".join(normalized.split())
    if not normalized:
        return "deny"
    if normalized in _APPROVE_RESPONSES:
        return "approve"
    if normalized in _EDIT_RESPONSES:
        return "edit"
    if normalized in _DENY_RESPONSES:
        return "deny"
    return "deny"


assert parse_confirmation('y') == 'approve'
assert parse_confirmation('no thanks') == 'deny'
assert parse_confirmation('edit please') == 'edit'
assert parse_confirmation('') == 'deny'
