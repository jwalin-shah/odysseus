"""Prompt templates for function implementation."""

def build_implement_fn_prompt(spec: str, signature: str, context: str = "") -> str:
    """Build a prompt asking the model to implement a function.

    Args:
        spec: Specification of the function.
        signature: Function signature.
        context: Optional context information.

    Returns:
        The formatted prompt string.
    """
    return (
        f"You are a Python expert. Implement the following function based on the specification and signature.\n\n"
        f"Specification:\n{spec}\n\n"
        f"Signature:\n{signature}\n\n"
        f"Context:\n{context}\n\n"
        f"Please provide the complete function implementation, including any necessary imports and docstrings.\n"
    )


def build_search_replace_prompt(file_path: str, search_text: str, replace_text: str, global_replace: bool = False) -> str:
    """Build a prompt asking an LLM to perform a search-and-replace operation on a file.

    Args:
        file_path: Path to the file to be modified.
        search_text: The text to search for in the file.
        replace_text: The text to replace the search text with.
        global_replace: If True, replace all occurrences; if False, replace only the first occurrence.

    Returns:
        The formatted prompt string.
    """
    scope = "all occurrences" if global_replace else "the first occurrence"
    return (
        f"You are a code editing assistant. Perform a search-and-replace operation on the file at '{file_path}'.\n\n"
        f"Search text:\n{search_text}\n\n"
        f"Replace text:\n{replace_text}\n\n"
        f"Replace {scope} of the search text with the replace text.\n"
    )
