"""logfmt_kv — Parse a single line of logfmt into a dict.

logfmt is a key=value format popularized by Heroku. Pairs are separated by
whitespace; values may be bare (terminated at the next whitespace) or
double-quoted (allows whitespace, escaped quotes, and escaped backslashes
inside). A key with no '=' is treated as a flag whose value is the empty
string. The result is a dict in input order; duplicate keys are overwritten
(last write wins — that matches how `logfmt` consumers treat repeated fields
when they collapse to a single dict).
"""


def logfmt_kv(line: str) -> dict[str, str]:
    """Parse one logfmt line into {key: value}.

    Empty or whitespace-only input returns an empty dict. Bare values are
    terminated by the next whitespace. Quoted values support `\\` and `\\"`.
    """
    out: dict[str, str] = {}
    i = 0
    n = len(line)
    while i < n:
        # Skip whitespace between pairs.
        while i < n and line[i].isspace():
            i += 1
        if i >= n:
            break

        # Read the key (up to '=' or whitespace).
        key_start = i
        while i < n and line[i] not in ("=", " ") and not line[i].isspace():
            i += 1
        if i == key_start:
            # Stray character (e.g. leading '=' or non-key token). Skip it.
            i += 1
            continue
        key = line[key_start:i]

        # Either a bare flag, a key=value, or a quoted value.
        if i >= n or line[i].isspace():
            out[key] = ""
            continue
        if line[i] != "=":
            # Unknown separator; treat as flag and continue.
            out[key] = ""
            continue
        i += 1  # consume '='

        # Value: bare or quoted.
        if i < n and line[i] == '"':
            i += 1  # consume opening quote
            val_chars: list[str] = []
            while i < n:
                c = line[i]
                if c == "\\" and i + 1 < n:
                    nxt = line[i + 1]
                    if nxt in ('"', "\\"):
                        val_chars.append(nxt)
                        i += 2
                        continue
                    # Any other backslash is preserved literally.
                    val_chars.append(c)
                    i += 1
                    continue
                if c == '"':
                    i += 1  # consume closing quote
                    break
                val_chars.append(c)
                i += 1
            out[key] = "".join(val_chars)
            continue

        # Bare value: read until whitespace.
        val_start = i
        while i < n and not line[i].isspace():
            i += 1
        out[key] = line[val_start:i]
    return out
