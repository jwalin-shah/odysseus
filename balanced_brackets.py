def is_balanced(s):
    """Check if brackets in string s are balanced."""
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    for ch in s:
        if ch in '([{':
            stack.append(ch)
        elif ch in ')]}':
            if not stack or stack[-1] != pairs[ch]:
                return False
            stack.pop()
    return not stack


def balanced_brackets(s):
    """Return True if brackets in the string are balanced."""
    return is_balanced(s)


if __name__ == "__main__":
    test_cases = [
        ("()", True),
        ("()[]{}", True),
        ("(]", False),
        ("([{}])", True),
        ("([)]", False),
        ("{[()()]}", True),
        ("", True),
        ("((", False),
        ("))", False),
        ("{[}]", False),
    ]
    for s, expected in test_cases:
        result = balanced_brackets(s)
        status = "PASS" if result == expected else "FAIL"
        print(f"{status}: balanced_brackets({s!r}) = {result} (expected {expected})")