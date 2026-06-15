def is_quota_error(exc: BaseException) -> bool:
    """
    Classify whether an exception represents a quota / rate-limit failure
    from an LLM provider by inspecting message text for tokens like '429',
    'quota', 'rate limit', or 'too many requests'.
    """
    message = str(exc).lower()
    quota_tokens = ('429', 'quota', 'rate limit', 'too many requests')
    return any(token in message for token in quota_tokens)
