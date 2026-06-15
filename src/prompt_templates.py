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
