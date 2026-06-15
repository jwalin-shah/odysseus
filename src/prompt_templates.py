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
        "Old text:\n{old_text}\n\n"
        "New text:\n{new_text}\n"
    ),
    "VERIFIER": (
        "You are a meticulous verifier. Your job is to carefully check the following task and determine "
        "whether the provided solution is correct, complete, and satisfies all stated requirements.\n\n"
        "Task:\n{task}\n\n"
        "Please analyze the solution step by step, identify any issues, and provide a clear verdict on "
        "whether it meets the specification."
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


def _verifier_template() -> str:
    """Return the verifier role prompt template string.

    The returned template contains a ``{task}`` placeholder that callers can
    fill in with the specific task to be verified.
    """
    return get_prompt_template("VERIFIER")


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


def build_search_replace_prompt(file_path: str, old_text: str, new_text: str, instruction: str = "") -> str:
    """Build a prompt asking an LLM to perform a search-and-replace operation on a file.

    Args:
        file_path: Path to the file to be modified.
        old_text: The text to search for in the file.
        new_text: The text to replace the old text with.
        instruction: Optional additional instruction to append to the prompt.

    Returns:
        The formatted prompt string.
    """
    template = get_prompt_template("SEARCH_REPLACE")
    prompt = template.format(
        file_path=file_path,
        old_text=old_text,
        new_text=new_text,
    )
    if instruction:
        prompt += f"\n\nAdditional instruction:\n{instruction}"
    return prompt
