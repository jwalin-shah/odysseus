import re


def find_secrets(text: str, patterns: list[re.Pattern]) -> list[tuple[int, int, str]]:
    """Scan text for matches against any pattern.

    Returns a list of (start, end, matched_string) tuples for every match
    found in ``text`` against any of the compiled ``patterns``. Matches do
    not overlap within a single pattern; however, matches from different
    patterns may overlap with one another.
    """
    results: list[tuple[int, int, str]] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            results.append((match.start(), match.end(), match.group()))
    return results
