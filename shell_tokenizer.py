def shell_tokenizer(s):
    """Tokenize a shell-like string into a list of tokens.

    Each quoted segment (single or double quoted) and each run of
    unquoted characters produces a separate token. Adjacent quoted and
    unquoted segments are NOT concatenated -- ``"a"b`` yields
    ``["a", "b"]``, not ``["ab"]``.
    """
    tokens = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '"':
            i += 1
            start = i
            while i < n and s[i] != '"':
                i += 1
            tokens.append(s[start:i])
            if i < n:
                i += 1  # skip closing quote
        elif ch == "'":
            i += 1
            start = i
            while i < n and s[i] != "'":
                i += 1
            tokens.append(s[start:i])
            if i < n:
                i += 1  # skip closing quote
        else:
            start = i
            while i < n and not s[i].isspace() and s[i] != '"' and s[i] != "'":
                i += 1
            tokens.append(s[start:i])
    return tokens