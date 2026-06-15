from src.circuit_breaker import CircuitBreaker
import time


def test_state_transitions() -> None:
    cb = CircuitBreaker(2, 0.05)
    assert cb.state == 'CLOSED'

    cb.record_failure()
    cb.record_failure()
    assert cb.state == 'OPEN' and cb.allow_request() is False

    time.sleep(0.06)
    assert cb.state == 'HALF_OPEN'

    cb.record_success()
    assert cb.state == 'CLOSED' and cb.allow_request() is True
