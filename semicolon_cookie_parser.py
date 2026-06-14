def semicolon_cookie_parser(cookie_string):
    """
    Parse a semicolon-separated cookie string into a dictionary.

    The cookie string format follows the HTTP Cookie header convention
    where each segment is a key=value pair separated by semicolons.
    Whitespace around keys and values is trimmed. Segments without an
    '=' sign are stored with an empty string as the value.

    Args:
        cookie_string: A string containing cookie segments separated by ';'.
                       May be None or empty.

    Returns:
        A dict mapping each cookie name to its value (as a string).
        Returns an empty dict if the input is empty, None, or contains
        only empty segments.
    """
    if not cookie_string:
        return {}

    result = {}
    # Split on semicolons to get individual segments.
    segments = cookie_string.split(';')
    for segment in segments:
        segment = segment.strip()
        if not segment:
            # Skip empty segments produced by leading/trailing/double semicolons.
            continue
        if '=' in segment:
            # split with maxsplit=1 so values containing '=' are preserved.
            key, value = segment.split('=', 1)
            result[key.strip()] = value.strip()
        else:
            # No '=' means a key with no associated value.
            result[segment] = ''
    return result