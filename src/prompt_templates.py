"""Prompt templates for function implementation."""

# Raw prompt templates indexed by name. Each template uses named format placeholders
# (e.g. ``{spec}``, ``{scope}``) that the corresponding ``build_*`` helpers fill in.
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
        "You are a Python expert. Implement the following function based on the specification and signature.\n\n"
        "Specification:\n{spec}\n\n"
        "Signature:\n{signature}\n\n"
        "Context:\n{context}\n\n"
        "Please provide the complete function implementation, including any necessary imports and docstrings.\n"
    ),
    "SEARCH_REPLACE": (
        "You are a code editing assistant. Perform a search-and-replace operation on the file at '{file_path}'.\n\n"
        "Search text:\n{search_text}\n\n"
        "Replace text:\n{replace_text}\n\n"
        "Replace {scope} of the search text with the replace text.\n"
    ),
    "IMPROVE_FILE": (
        "You are a senior software engineer. Suggest improvements for the following file based on the specified goals.\n\n"
        "File path: {file_path}\n\n"
        "Current content:\n{file_content}\n\n"
        "Improvement goals:\n{goals}\n\n"
        "Please provide concrete, actionable improvements that address each of these goals. Show the suggested changes clearly so they can be applied to the file."
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


def build_implement_fn_prompt(spec: str, signature: str, context: str = "") -> str:
    """Build a prompt asking the model to implement a function.

    Args:
        spec: Specification of the function.
        signature: Function signature.
        context: Optional context information.

    Returns:
        The formatted prompt string.
    """
    template = get_prompt_template("IMPLEMENT_FN")
    return template.format(spec=spec, signature=signature, context=context)


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


def build_improve_file_prompt(file_path: str, file_content: str, goals: list) -> str:
    """Build a prompt asking the model to suggest improvements for an existing file.

    Args:
        file_path: Path to the file that should be improved.
        file_content: The current contents of the file.
        goals: A list of improvement goal keywords (e.g. ``["performance"]`` or
            ``["performance", "readability"]``).

    Returns:
        The formatted prompt string.
    """
    template = get_prompt_template("IMPROVE_FILE")
    return template.format(file_path=file_path, file_content=file_content, goals=goals)
