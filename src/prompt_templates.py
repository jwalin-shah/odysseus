"""Prompt templates for code generation tasks."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class PromptTemplate:
    """A simple prompt template with named variables and a body."""
    name: str
    variables: List[str] = field(default_factory=list)
    body: str = ""


def implement_fn_template() -> PromptTemplate:
    """Build and return the IMPLEMENT_FN prompt template.

    The template instructs the model to implement a function from its
    signature and specification.
    """
    body = (
        "You are an expert Python developer.\n"
        "Your task is to implement the function described below.\n"
        "Use only the Python standard library unless the specification "
        "explicitly requires third-party packages.\n\n"
        "Function signature:\n"
        "{{function_signature}}\n\n"
        "Specification:\n"
        "{{spec}}\n\n"
        "Requirements:\n"
        "1. Implement the function exactly as described in the specification.\n"
        "2. Preserve the given function signature, including parameters, "
        "type hints, and return annotation.\n"
        "3. Write clean, idiomatic, and well-documented code.\n"
        "4. Include appropriate error handling and edge-case handling.\n"
        "5. Do not include example usage, test cases, or any code outside "
        "the function definition.\n\n"
        "Output the full implementation below:\n"
    )

    return PromptTemplate(
        name="IMPLEMENT_FN",
        variables=["function_signature", "spec"],
        body=body,
    )
