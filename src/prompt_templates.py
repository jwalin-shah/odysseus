from typing import Dict


class PromptTemplate:
    """A simple prompt template with a name and a template string."""

    def __init__(self, name: str, template: str = "") -> None:
        self.name = name
        self.template = template

    def __repr__(self) -> str:
        return f"PromptTemplate(name={self.name!r})"


_REGISTRY: Dict[str, PromptTemplate] = {
    "IMPLEMENT_FN": PromptTemplate(
        "IMPLEMENT_FN",
        "Implement the following function.\n\nSignature:\n{function_signature}\n\nSpec:\n{spec}",
    ),
    "REVIEW": PromptTemplate(
        "REVIEW",
        "Review the following code for correctness, style, and edge cases:\n\n{code}",
    ),
}


def get_template(name: str) -> PromptTemplate:
    """Look up a registered prompt template by name.

    Args:
        name: The name of the prompt template to retrieve.

    Returns:
        The registered :class:`PromptTemplate` matching ``name``.

    Raises:
        KeyError: If no template is registered under ``name``.
    """
    return _REGISTRY[name]
