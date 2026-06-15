import time


class CircuitBreaker:
    def __init__(self, fail_threshold: int, cooldown: float) -> None:
        self.fail_threshold = fail_threshold
        self.cooldown = cooldown
        self.state = 'CLOSED'
        self.fail_count = 0
        self._opened_at = 0.0
