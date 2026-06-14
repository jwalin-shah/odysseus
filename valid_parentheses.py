def is_valid(s: str) -> bool:
    stack = []
    mapping = {')': '(', ']': '[', '}': '{'}
    for ch in s:
        if ch in mapping:
            if not stack or stack[-1] != mapping[ch]:
                return False
            stack.pop()
        else:
            stack.append(ch)
    return not stack


def longest_valid(s: str) -> int:
    stack = [-1]
    max_len = 0
    for i, ch in enumerate(s):
        if ch == '(':
            stack.append(i)
        else:
            if len(stack) > 1:
                stack.pop()
                max_len = max(max_len, i - stack[-1])
            else:
                stack[-1] = i
    return max_len