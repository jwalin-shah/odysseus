import time


class CircuitBreaker:
    def __init__(self, fail_threshold: int, cooldown: float) -> None:
        self.fail_threshold = fail_threshold
        self.cooldown = cooldown
        self.state = 'closed'
        self.failures = 0
        self.last_failure_time = 0.0
