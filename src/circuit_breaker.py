import time

class CircuitBreaker:
    def __init__(self, failure_threshold, recovery_timeout):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self._state = 'closed'
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self._state = 'open'
    
    def allow_request(self):
        if self._state == 'open':
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self._state = 'half_open'
                return True
            return False
        return True
    
    @property
    def state(self) -> str:
        return self._state
