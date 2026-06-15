class CircuitBreaker:
    def __init__(self, fail_threshold, recovery_timeout):
        self.fail_threshold = fail_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = 'CLOSED'

    def record_failure(self) -> str:
        self.failure_count += 1
        if self.failure_count >= self.fail_threshold:
            self.state = 'OPEN'
        return self.state
