import time


class CircuitBreaker:
    def __init__(self, fail_threshold: int, reset_timeout: float) -> None:
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.fail_count: int = 0
        self.last_failure_time: float | None = None
        self.state: str = 'CLOSED'

    def record_failure(self) -> None:
        self.fail_count += 1
        self.last_failure_time = time.time()
        if self.fail_count >= self.fail_threshold:
            self.state = 'OPEN'
