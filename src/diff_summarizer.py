"""Line-based diff summarizer and its fixture-driven test."""


def summarize_diff(old: str, new: str) -> dict:
    """Count how many unique lines were added and removed between two texts.

    Returns a dict with keys ``"added"`` and ``"removed"`` mapping to the
    number of lines present in one input but not the other.
    """
    old_lines = set(old.splitlines())
    new_lines = set(new.splitlines())
    return {
        "added": len(new_lines - old_lines),
        "removed": len(old_lines - new_lines),
    }


def fixture_pair() -> tuple:
    """Return a canonical ``(old, new)`` pair exercising one add and one remove."""
    old = "alpha\nbeta\ngamma"
    new = "alpha\ngamma\ndelta"
    return old, new


def test_summarize_diff_on_fixture() -> None:
    """summarize_diff reports one added and one removed line on the fixture pair."""
    old, new = fixture_pair()
    assert summarize_diff(old, new) == {"added": 1, "removed": 1}
    old, new = fixture_pair()
    assert summarize_diff(old, new)["added"] == summarize_diff(old, new)["removed"]
