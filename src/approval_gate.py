"""Parse CLI approval gate responses into structured decisions."""

from __future__ import annotations

# Tokens that signal approval (single-shot).
_POSITIVE_TOKENS = frozenset({"y", "yes"})

# Tokens that signal explicit denial.
_NEGATIVE_TOKENS = frozenset({"n", "no"})

# Tokens that signal "approve and remember this decision".
_REMEMBER_TOKENS = frozenset({"always"})


def parse_confirmation_response(text: str) -> dict:
    """Parse raw CLI input into a structured approval decision.

    Returns a dict with three fields:
        - allow (bool): whether the action is approved.
        - remember (str): empty for one-shot, otherwise a persistence key
          such as ``"always"``.
        - reason (str): free-form justification supplied by the user.

    Empty input and any unrecognized token default to denial.
    """
    result = {"allow": False, "remember": "", "reason": ""}

    if not isinstance(text, str):
        return result

    cleaned = text.strip()
    if not cleaned:
        return result

    lowered = cleaned.lower()
    tokens = lowered.split(maxsplit=1)
    head = tokens[0]
    tail = tokens[1] if len(tokens) > 1 else ""

    # Standalone "always" -> approve and remember, optional trailing reason.
    if head in _REMEMBER_TOKENS:
        return {
            "allow": True,
            "remember": "always",
            "reason": tail.strip(),
        }

    # Positive responses may carry a remember modifier or a reason.
    if head in _POSITIVE_TOKENS:
        remember = ""
        reason = tail.strip()
        if reason:
            reason_tokens = reason.split()
            if reason_tokens[0] in _REMEMBER_TOKENS:
                remember = "always"
                reason = " ".join(reason_tokens[1:]).strip()
        return {"allow": True, "remember": remember, "reason": reason}

    # Explicit negative responses capture the reason but never remember.
    if head in _NEGATIVE_TOKENS:
        return {"allow": False, "remember": "", "reason": tail.strip()}

    # Unknown input falls through to the safe default: deny.
    return result
