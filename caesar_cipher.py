def encrypt(text: str, shift: int) -> str:
    result = []
    for char in text:
        if char.isalpha():
            base = ord('A') if char.isupper() else ord('a')
            result.append(chr((ord(char) - base + shift) % 26 + base))
        else:
            result.append(char)
    return ''.join(result)


def decrypt(text: str, shift: int) -> str:
    return encrypt(text, -shift)


def crack(text: str) -> tuple[int, str]:
    freq = {}
    total = 0
    for char in text.lower():
        if char.isalpha():
            freq[char] = freq.get(char, 0) + 1
            total += 1
    if total == 0:
        return 0, text
    most_common = max(freq, key=freq.get)
    shift = (ord(most_common) - ord('e')) % 26
    return shift, decrypt(text, shift)


def rot13(text: str) -> str:
    return encrypt(text, 13)