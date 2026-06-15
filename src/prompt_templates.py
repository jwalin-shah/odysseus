def list_available_templates() -> list[str]:
    """Return the canonical names of all prompt templates registered in the library."""
    return ["IMPLEMENT_FN", "IMPROVE_FILE", "REVIEW", "SEARCH_REPLACE"]
