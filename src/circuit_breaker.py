import time


class CircuitBreaker:
    """Circuit breaker implementation.

    States:
        closed: requests are allowed.
        open: requests are blocked until cooldown elapses.
        half_open: allows a trial request after cooldown.
    """

    def __init__(self, failure_threshold: int, cooldown_seconds: float):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None

    def record_failure(self) -> None:
        """Record a failure and open the circuit if threshold is reached."""
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.last_failure_time = time.time()

    def record_success(self) -> None:
        """Reset the breaker to closed state on success."""
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None

    def allow_request(self) -> bool:
        """Return True if a call may proceed; transition OPEN to HALF_OPEN once cooldown elapses."""
        if self.state == "closed":
            return True
        if self.state == "half_open":
            return True
        if self.state == "open":
            if (
                self.last_failure_time is not None
                and (time.time() - self.last_failure_time) >= self.cooldown_seconds
            ):
                self.state = "half_open"
                return True
            return False
        return False
