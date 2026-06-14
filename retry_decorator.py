import functools
import time
import random
import logging

logger = logging.getLogger(__name__)


def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,), jitter=False, logger_=None):
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including the first call).
        delay: Initial delay between retries in seconds.
        backoff: Multiplier applied to the delay after each retry.
        exceptions: Tuple of exception classes to catch and retry on.
        jitter: If True, randomize the wait time to avoid thundering herd.
        logger_: Optional custom logger instance. Falls back to module logger.

    Raises:
        The last caught exception if all attempts fail.

    Example:
        @retry(max_attempts=5, delay=2, backoff=2, jitter=True)
        def fetch_data():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            log = logger_ or logger
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt >= max_attempts:
                        log.error(
                            "Final attempt %d/%d failed for %s: %s",
                            attempt, max_attempts, func.__name__, exc,
                        )
                        raise
                    wait = current_delay
                    if jitter:
                        wait = current_delay * (0.5 + random.random())
                    log.warning(
                        "Attempt %d/%d failed for %s: %s. Retrying in %.2fs...",
                        attempt, max_attempts, func.__name__, exc, wait,
                    )
                    time.sleep(wait)
                    current_delay *= backoff
            # Unreachable, but keeps type checkers happy.
            return None
        return wrapper
    return decorator