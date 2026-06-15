"""API key router utilities for handling quota and rate-limit errors."""


def is_quota_error(status_code: int, body: str) -> bool:
    """Return True when an HTTP response indicates a quota / rate-limit error requiring key rotation.

    Detection is based on:
    - HTTP status codes commonly associated with quota or rate-limit issues
      (e.g. 429 Too Many Requests, 402 Payment Required).
    - Presence of quota / rate-limit related keywords in the response body
      (case-insensitive).

    Args:
        status_code: The HTTP status code from the response.
        body: The response body as a string.

    Returns:
        True if the response indicates a quota or rate-limit error, False otherwise.
    """
    # Status codes that commonly indicate quota / rate-limit issues.
    quota_status_codes = {429, 402}

    # Keywords / phrases that typically appear in quota / rate-limit error responses.
    quota_indicators = (
        "rate limit",
        "rate_limit",
        "ratelimit",
        "quota",
        "insufficient_quota",
        "quota_exceeded",
        "too many requests",
        "request limit",
        "limit reached",
    )

    if status_code in quota_status_codes:
        return True

    body_lower = body.lower() if body else ""
    return any(indicator in body_lower for indicator in quota_indicators)
