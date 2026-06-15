"""Prompt templates for function implementation."""

# Raw prompt templates indexed by name. Each template uses named format placeholders
# (e.g. ``{func_spec}``, ``{language}``, ``{context}``) that the corresponding ``build_*`` helpers fill in.
_PROMPT_TEMPLATES = {
    "REVIEW": (
        "You are a senior software engineer performing a thorough code review.\n\n"
        "Please review the following code and provide detailed feedback on:\n"
        "- Correctness: Does the code behave as intended for all valid inputs?\n"
        "- Design: Is the code well-structured, modular, and maintainable?\n"
        "- Performance: Are there any obvious performance issues or inefficiencies?\n"
        "- Security: Are there any security vulnerabilities or unsafe practices?\n"
        "- Style: Does the code follow language idioms and project conventions?\n"
        "- Tests: Are there sufficient tests, and are edge cases covered?\n\n"
        "Code to review:\n{code}\n\n"
        "Provide your review as a clear, actionable list of findings with suggested improvements."
    ),
    "IMPLEMENT_FN": (
        "You are a {language} expert. Implement the following function based on the specification and signature.\n\n"
        "Function specification and signature:\n{func_spec}\n\n"
        "Context:\n{context}\n\n"
        "Please provide the complete function implementation, including any necessary imports and docstrings.\n"
    ),
    "SEARCH_REPLACE": (
        "You are a code editing assistant. Perform a search-and-replace operation on the file at '{file_path}'.\n\n"
        "Search text:\n{search_text}\n\n"
        "Replace text:\n{replace_text}\n\n"
        "Replace {scope} of the search text with the replace text.\n"
    ),
}


def get_prompt_template(name: str) -> str:
    """Return the raw template string for a named prompt template.

    Args:
        name: The identifier of the template to retrieve (e.g. ``"REVIEW"``,
            ``"IMPLEMENT_FN"``, ``"SEARCH_REPLACE"``).

    Returns:
        The raw template string, containing named ``str.format`` placeholders
        that callers can fill in themselves.

    Raises:
        KeyError: If ``name`` does not match any registered template.
    """
    return _PROMPT_TEMPLATES[name]


def build_implement_fn_prompt(func_spec: str, language: str = "python", context: str = "") -> str:
    """Build a prompt instructing the model to implement a function from a signature/spec.

    Args:
        func_spec: The function specification and signature text.
        language: The target programming language for the implementation
            (default: ``"python"``).
        context: Optional additional context information to include in the prompt.

    Returns:
        The formatted prompt string ready to send to a language model.
    """
    template = get_prompt_template("IMPLEMENT_FN")
    return template.format(func_spec=func_spec, language=language, context=context)


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
    template = get_prompt_template("SEARCH_REPLACE")
    return template.format(
        file_path=file_path,
        search_text=search_text,
        replace_text=replace_text,
        scope=scope,
    )
