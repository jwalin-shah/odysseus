def fixture_pair() -> tuple[str, str]:
    """Return a deterministic (old, new) text pair used as a diff summarizer fixture.

    The pair is chosen so that:
    * both entries are non-empty strings,
    * the two entries differ (so a diff has content to summarize),
    * the old text contains the substring ``beta`` and the new text contains
      the substring ``epsilon`` -- giving tests a stable anchor to assert on.
    """
    old_text = (
        "Project status: alpha phase complete.\n"
        "Next milestone: beta release in Q2.\n"
        "Pending items: documentation, performance tuning.\n"
    )
    new_text = (
        "Project status: alpha phase complete.\n"
        "Next milestone: epsilon release in Q3.\n"
        "Pending items: documentation, performance tuning, localization.\n"
    )
    return old_text, new_text
