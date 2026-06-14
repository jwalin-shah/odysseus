def logfmt_kv(s):
    """
    Parse a logfmt-formatted string into a dictionary of key-value pairs.

    logfmt is a structured logging format consisting of key=value pairs
    separated by whitespace. Values that contain whitespace may be wrapped
    in double quotes; inside quoted strings, a backslash escapes the next
    character (so \\" produces a literal quote).

    Examples
    --------
    >>> logfmt_kv("key=value")
    {'key': 'value'}
    >>> logfmt_kv('msg="hello world" level=info')
    {'msg': 'hello world', 'level': 'info'}
    >>> logfmt_kv("a=1 b c=3")
    {'a': '1', 'b': '', 'c': '3'}
    """
    result = {}
    i = 0
    n = len(s)

    while i < n:
        # Skip leading whitespace between pairs.
        while i < n and s[i] == ' ':
            i += 1
        if i >= n:
            break

        # Parse the key (stops at '=' or whitespace).
        key_start = i
        while i < n and s[i] not in (' ', '='):
            i += 1
        key = s[key_start:i]

        if not key:
            # Malformed input like "=value" or leading "=": stop safely.
            break

        # Key without a value (e.g. trailing "flag").
        if i >= n or s[i] == ' ':
            result[key] = ""
            continue

        # Consume the '=' separator.
        i += 1

        # Parse the value, either quoted (with escapes) or bare.
        if i < n and s[i] == '"':
            i += 1
            value_parts = []
            while i < n and s[i] != '"':
                if s[i] == '\\' and i + 1 < n:
                    nxt = s[i + 1]
                    if nxt == 'n':
                        value_parts.append('\n')
                    elif nxt == 't':
                        value_parts.append('\t')
                    elif nxt == 'r':
                        value_parts.append('\r')
                    else:
                        value_parts.append(nxt)
                    i += 2
                else:
                    value_parts.append(s[i])
                    i += 1
            if i < n:
                i += 1  # skip the closing quote
            result[key] = ''.join(value_parts)
        else:
            value_start = i
            while i < n and s[i] != ' ':
                i += 1
            result[key] = s[value_start:i]

    return result