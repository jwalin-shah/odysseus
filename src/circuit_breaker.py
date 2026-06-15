import time


class CircuitBreaker:
    def __init__(self, failure_threshold, cooldown):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self.failure_count = 0
        self.state = 'CLOSED'
        self.last_failure_time = None

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'

    def record_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'

    def allow_request(self) -> bool:
        if self.state == 'OPEN':
            if self.last_failure_time is not None and (time.time() - self.last_failure_time) >= self.cooldown:
                self.state = 'HALF_OPEN'
                return True
            return False
        return True
