"""Prompt templates for function implementation."""


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


def format_prompt_template(template: str, **kwargs: str) -> str:
    """Substitute ``{name}`` style placeholders in a template string.

    Args:
        template: The template string containing ``{name}`` style placeholders.
        **kwargs: Keyword arguments whose values will be substituted into the
            placeholders. Each key in ``kwargs`` must be a valid Python identifier
            and must match a placeholder name in ``template``.

    Returns:
        The formatted template string with all placeholders replaced by the
        corresponding keyword argument values.

    Raises:
        KeyError: If ``template`` contains a placeholder whose name is not
            present in ``kwargs``.
    """
    return template.format(**kwargs)
