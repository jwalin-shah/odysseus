import time


class CircuitBreaker:
    def __init__(self, failure_threshold, reset_timeout):
        """Initialize the circuit breaker.

        Args:
            failure_threshold: Number of failures before opening the circuit.
            reset_timeout: Time in seconds before attempting to close the circuit again.
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.fail_count = 0
        self.state = 'CLOSED'
        self.last_failure_time = None

    def record_failure(self):
        """Record a failure and potentially open the circuit."""
        self.fail_count += 1
        if self.fail_count >= self.failure_threshold:
            self.state = 'OPEN'
            self.last_failure_time = time.time()

    def record_success(self):
        """Record a success, reset the failure counter, and close the circuit."""
        self.fail_count = 0
        self.state = 'CLOSED'
