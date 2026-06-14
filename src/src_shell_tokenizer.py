def shell_tokenize(s):
    """Tokenize a shell-like string into a list of tokens.

    Handles:
    - Whitespace-separated words
    - Single quotes (literal, no escaping inside)
    - Double quotes (with backslash escapes for \", \\, \$, \`, \\n)
    - Backslash escapes outside quotes
    - Empty quoted strings produce an empty-string token
    """
    tokens = []
    current = []
    in_single = False
    in_double = False
    i = 0
    n = len(s)
    has_content = False  # Tracks whether a token has been started

    while i < n:
        c = s[i]

        if in_single:
            if c == "'":
                in_single = False
            else:
                current.append(c)
            i += 1
        elif in_double:
            if c == '"':
                in_double = False
                i += 1
            elif c == '\\' and i + 1 < n and s[i + 1] in ('"', '\\', '$', '`', '\n'):
                current.append(s[i + 1])
                i += 2
            else:
                current.append(c)
                i += 1
        else:
            if c.isspace():
                if has_content:
                    tokens.append(''.join(current))
                    current = []
                    has_content = False
                i += 1
            elif c == "'":
                in_single = True
                has_content = True
                i += 1
            elif c == '"':
                in_double = True
                has_content = True
                i += 1
            elif c == '\\':
                has_content = True
                if i + 1 < n:
                    current.append(s[i + 1])
                    i += 2
                else:
                    current.append(c)
                    i += 1
            else:
                current.append(c)
                has_content = True
                i += 1

    if has_content:
        tokens.append(''.join(current))

    return tokens


if __name__ == "__main__":
    # Simple smoke test when run directly
    samples = [
        "",
        "hello",
        "hello world",
        "'hello world'",
        '"hello world"',
        "''",
        '""',
        "ls -la /tmp",
        "a'b'c",
    ]
    for s in samples:
        print(repr(s), "->", shell_tokenize(s))