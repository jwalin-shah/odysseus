"""In-memory session policy for caching approval decisions."""


class ApprovalPolicy:
    """Caches per-action 'always allow' or 'never allow' verdicts to skip repeat prompts."""

    def __init__(self) -> None:
        """Initialize the policy with an empty decision cache."""
        self._decisions: dict[str, str] = {}

    def should_prompt(self, action: str) -> bool:
        """Return True if a prompt should be shown for the given action.

        Returns False if a verdict has already been recorded for this action.
        """
        return action not in self._decisions

    def record(self, action: str, decision: str) -> None:
        """Record an approval verdict for the given action.

        Args:
            action: The action identifier.
            decision: Either 'always' (skip future prompts) or 'never' (block).
        """
        self._decisions[action] = decision

    def is_blocked(self, action: str) -> bool:
        """Return True if the action has been recorded with a 'never' verdict."""
        return self._decisions.get(action) == "never"
