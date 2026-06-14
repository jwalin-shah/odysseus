def encode(s: str) -> str:
    if not s:
        return ""
    result = []
    i = 0
    while i < len(s):
        count = 1
        while i + 1 < len(s) and s[i] == s[i + 1]:
            count += 1
            i += 1
        if count > 1:
            result.append(str(count) + s[i])
        else:
            result.append(s[i])
        i += 1
    return "".join(result)


def decode(s: str) -> str:
    if not s:
        return ""
    result = []
    i = 0
    while i < len(s):
        num_str = ""
        while i < len(s) and s[i].isdigit():
            num_str += s[i]
            i += 1
        if num_str:
            count = int(num_str)
        else:
            count = 1
        if i >= len(s):
            raise ValueError("Malformed RLE input: number without trailing character")
        if s[i].isdigit():
            raise ValueError("Malformed RLE input: unexpected digit")
        result.append(s[i] * count)
        i += 1
    return "".join(result)