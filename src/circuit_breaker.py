class CircuitBreaker:
    def __init__(self, threshold: int, timeout: float):
        self._failure_count = 0
        self._threshold = threshold
        self._timeout = timeout
        self.state = 'closed'

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self._threshold:
            self.state = 'open'
