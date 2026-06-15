import time


class CircuitBreaker:
    def __init__(self, failure_threshold, reset_timeout):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failure_count = 0
        self.state = 'closed'
        self._last_failure_time = None

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self.state = 'open'

    def reset(self):
        self._failure_count = 0
        self.state = 'closed'
        self._last_failure_time = None
