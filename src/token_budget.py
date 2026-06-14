"""Token budget tracking for LLM sessions."""

from dataclasses import dataclass


@dataclass
class TokenBudget:
    """Tracks input/output token usage per session.

    Emits a warning (via ``should_warn``) once usage reaches 80% of the
    configured limit and hard-stops (via ``is_exhausted``) at 95%.
    """

    limit: int
    input_tokens: int = 0
    output_tokens: int = 0
    warning_threshold: float = 0.80
    hard_stop_threshold: float = 0.95

    def add(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Record token usage from a single LLM call."""
        self.input_tokens += max(0, int(input_tokens))
        self.output_tokens += max(0, int(output_tokens))

    def used(self) -> int:
        """Total tokens consumed so far."""
        return self.input_tokens + self.output_tokens

    def remaining(self) -> int:
        """Tokens still available before the hard stop."""
        return max(0, self.limit - self.used())

    def usage_ratio(self) -> float:
        """Fraction of the limit consumed (0.0 to 1.0+)."""
        if self.limit <= 0:
            return 1.0
        return self.used() / self.limit

    def should_warn(self) -> bool:
        """True once usage crosses the soft warning threshold (default 80%)."""
        return self.usage_ratio() >= self.warning_threshold

    def is_exhausted(self) -> bool:
        """True once usage crosses the hard-stop threshold (default 95%)."""
        return self.usage_ratio() >= self.hard_stop_threshold

    def status_line(self) -> str:
        """One-line summary suitable for surfacing in prompts or logs."""
        return (
            f"Token budget: {self.used()}/{self.limit} used, "
            f"{self.remaining()} remaining "
            f"({self.usage_ratio() * 100:.1f}%)"
        )