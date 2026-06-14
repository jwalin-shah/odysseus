def is_palindrome(s: str) -> bool:
    """Check if string is palindrome ignoring non-alpha characters (case-insensitive)."""
    filtered = [c.lower() for c in s if c.isalpha()]
    return filtered == filtered[::-1]


def longest_palindromic_substring(s: str) -> str:
    """Find longest palindromic substring using expand around center O(n^2)."""
    if not s:
        return ""

    def expand_around_center(left: int, right: int) -> str:
        while left >= 0 and right < len(s) and s[left] == s[right]:
            left -= 1
            right += 1
        return s[left + 1:right]

    longest = ""
    for i in range(len(s)):
        # Odd length palindromes
        palindrome1 = expand_around_center(i, i)
        if len(palindrome1) > len(longest):
            longest = palindrome1

        # Even length palindromes
        palindrome2 = expand_around_center(i, i + 1)
        if len(palindrome2) > len(longest):
            longest = palindrome2

    return longest


def count_palindromic_substrings(s: str) -> int:
    """Count palindromic substrings using expand around center."""
    if not s:
        return 0

    def expand_around_center(left: int, right: int) -> int:
        count = 0
        while left >= 0 and right < len(s) and s[left] == s[right]:
            count += 1
            left -= 1
            right += 1
        return count

    total = 0
    for i in range(len(s)):
        total += expand_around_center(i, i)      # Odd length
        total += expand_around_center(i, i + 1)  # Even length

    return total


def is_anagram(s1: str, s2: str) -> bool:
    """Check if two strings are anagrams of each other."""
    from collections import Counter
    return Counter(s1) == Counter(s2)


def minimum_window_substring(s: str, t: str) -> str:
    """Find minimum window substring of s containing all characters of t (sliding window O(n))."""
    from collections import Counter

    if not t or not s:
        return ""

    t_count = Counter(t)
    window_count = Counter()

    have = 0
    need = len(t_count)
    result = [-1, -1]
    result_len = float('inf')
    left = 0

    for right in range(len(s)):
        char = s[right]
        window_count[char] += 1

        if char in t_count and window_count[char] == t_count[char]:
            have += 1

        while have == need:
            # Update result
            if (right - left + 1) < result_len:
                result = [left, right]
                result_len = right - left + 1

            # Try to shrink window from left
            char_left = s[left]
            window_count[char_left] -= 1
            if char_left in t_count and window_count[char_left] < t_count[char_left]:
                have -= 1
            left += 1

    return s[result[0]:result[1] + 1] if result_len != float('inf') else ""