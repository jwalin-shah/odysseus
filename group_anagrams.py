from collections import Counter

def are_anagrams(a: str, b: str) -> bool:
    return Counter(a) == Counter(b)

def group_anagrams(words: list[str]) -> list[list[str]]:
    groups: dict[str, list[str]] = {}
    for word in words:
        key = ''.join(sorted(word))
        if key not in groups:
            groups[key] = []
        groups[key].append(word)
    
    result: list[list[str]] = []
    for group in groups.values():
        group.sort()
        result.append(group)
    
    result.sort(key=lambda g: g[0])
    return result