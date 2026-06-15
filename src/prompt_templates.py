"""Prompt templates for function implementation."""


_TEMPLATES: dict = {}


def register_template(name: str):
    """Decorator to register a prompt template builder function.

    Args:
        name: The template name to register under.

    Returns:
        A decorator that stores the function in the template registry.
    """
    def decorator(func):
        _TEMPLATES[name] = func
        return func
    return decorator


def list_template_names() -> list[str]:
    """Return the names of all prompt templates registered in the library."""
    return list(_TEMPLATES.keys())


@register_template('IMPLEMENT_FN')
def build_implement_fn_prompt(name: str, signature: str, docstring: str | None = None, language: str = 'python') -> str:
    """Build a prompt instructing an LLM to implement a function.

    Args:
        name: The name of the function to implement.
        signature: The function signature line(s).
        docstring: Optional docstring describing the function's behavior.
        language: The programming language for the implementation (default 'python').

    Returns:
        The formatted prompt string.
    """
    parts = [
        f"You are a {language} expert. Please implement the following function.",
        f"Function name: {name}",
        f"Signature:\n{signature}",
    ]
    if docstring:
        parts.append(f"Docstring:\n{docstring}")
    parts.append(
        f"Please write the complete implementation of the `{name}` function in {language}, "
        f"including any necessary imports and type hints."
    )
    return "\n\n".join(parts) + "\n"


@register_template('REVIEW')
def build_review_prompt(name: str, code: str, focus: str | None = None) -> str:
    """Build a prompt instructing an LLM to review code.

    Args:
        name: The name of the function or component being reviewed.
        code: The code to review.
        focus: Optional aspect to focus the review on (e.g., 'security', 'performance').

    Returns:
        The formatted prompt string.
    """
    parts = [
        f"You are a code review expert. Please review the following code.",
        f"Target: {name}",
        f"Code:\n{code}",
    ]
    if focus:
        parts.append(f"Focus on: {focus}")
    parts.append(
        f"Please provide a detailed review of the `{name}` code, "
        f"pointing out any issues, suggestions for improvement, and best practices."
    )
    return "\n\n".join(parts) + "\n"
