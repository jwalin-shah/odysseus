class CircuitBreaker:
    def __init__(self, failure_threshold, recovery_timeout):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._state = 'closed'

    @property
    def state(self):
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        if self._state == 'half_open':
            self._state = 'closed'
