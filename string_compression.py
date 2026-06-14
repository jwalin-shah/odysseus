def compress(s: str) -> str:
    """Compress a string using run-length encoding; return original if longer."""
    if not s:
        return s
    result = []
    count = 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1]:
            count += 1
        else:
            result.append(s[i - 1] + str(count))
            count = 1
    result.append(s[-1] + str(count))
    compressed = "".join(result)
    return compressed if len(compressed) < len(s) else s


def decompress(s: str) -> str:
    if not s:
        return s
    result = []
    i = 0
    while i < len(s):
        ch = s[i]
        i += 1
        num_str = []
        while i < len(s) and s[i].isdigit():
            num_str.append(s[i])
            i += 1
        count = int("".join(num_str)) if num_str else 1
        result.append(ch * count)
    return "".join(result)


def is_unique(s: str) -> bool:
    checker = 0
    for ch in s:
        val = ord(ch)
        if val > 127:
            return _is_unique_set(s)
        if (checker & (1 << val)) > 0:
            return False
        checker |= (1 << val)
    return True


def _is_unique_set(s: str) -> bool:
    seen = set()
    for ch in s:
        if ch in seen:
            return False
        seen.add(ch)
    return True


def has_all_unique(s: str) -> bool:
    seen = set()
    for ch in s:
        if ch in seen:
            return False
        seen.add(ch)
    return True