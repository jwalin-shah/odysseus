import re


def parse_confirmation_response(text: str) -> str:
    """Parse raw CLI confirmation input into a normalized token.
    
    Returns one of: 'approve', 'deny', 'approve_all', or 'invalid'.
    """
    if text is None:
        return 'invalid'
    
    # Normalize: strip whitespace and lowercase
    normalized = text.strip().lower()
    
    if not normalized:
        return 'invalid'
    
    # Define accepted tokens for each category
    approve_tokens = {
        'y', 'yes', 'yeah', 'yep', 'yup', 'sure', 'ok', 'okay',
        'approve', 'approved', 'a', 'true', 't', '1', 'confirm',
        'proceed', 'go', 'accept'
    }
    
    deny_tokens = {
        'n', 'no', 'nah', 'nope', 'nay', 'deny', 'denied', 'reject',
        'rejected', 'd', 'false', 'f', '0', 'decline', 'refuse',
        'stop', 'cancel', 'negative'
    }
    
    approve_all_tokens = {
        'always', 'all', 'approve-all', 'approve_all', 'yes-all',
        'yes_all', 'a-all', 'a_all', 'y-all', 'y_all', 'a*',
        'y*', 'yes-all', 'all-yes', 'all_yes'
    }
    
    # Check for approve_all first (more specific)
    if normalized in approve_all_tokens:
        return 'approve_all'
    
    if normalized in approve_tokens:
        return 'approve'
    
    if normalized in deny_tokens:
        return 'deny'
    
    return 'invalid'
