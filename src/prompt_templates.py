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
    "REFACTOR": (
        "You are a senior software engineer tasked with refactoring code to improve its quality.\n\n"
        "Please refactor the following code to improve:\n"
        "- Readability and clarity\n"
        "- Modularity and reusability\n"
        "- Performance where applicable\n"
        "- Adherence to best practices and idioms\n\n"
        "Code to refactor:\n{code}\n\n"
        "Constraints:\n{constraints}\n\n"
        "Provide the refactored code along with a brief explanation of the changes made."
    ),
}


def list_prompt_templates() -> list:
    """Return the list of registered prompt template names.

    Returns:
        A list of strings, where each string is the name of a registered
        prompt template that can be passed to :func:`get_prompt_template`.
    """
    return list(_PROMPT_TEMPLATES.keys())


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
