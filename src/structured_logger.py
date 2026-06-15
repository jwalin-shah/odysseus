def validate_level(level: str) -> str:
    """Normalize a log level string to uppercase and verify it is one of the accepted levels.
    
    Args:
        level: The log level string to validate.
    
    Returns:
        The normalized uppercase log level.
    
    Raises:
        ValueError: If the level is not one of the accepted log levels.
    """
    normalized = level.upper()
    accepted_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    if normalized not in accepted_levels:
        raise ValueError(
            f"Invalid log level: {level}. "
            f"Must be one of: {', '.join(sorted(accepted_levels))}"
        )
    return normalized
