"""Prompt templates for function implementation."""

# Raw prompt templates indexed by name. Each template uses named format placeholders
# (e.g. ``{spec}``, ``{scope}``) that the corresponding ``build_*`` helpers fill in.
_PROMPT_TEMPLATES = {
    "REVIEW": (
        "You are a senior software engineer performing a thorough code review of the file at '{file_path}'.\n\n"
        "Please review the following code and provide detailed feedback focused on: {review_focus}.\n"
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
    "CRITIC": (
        "You are a critic. Your role is to critique the risks and weaknesses of a proposed approach for the given task.\n\n"
        "{task_desc}\n\n"
        "Please provide a thorough critique covering:\n"
        "- Potential risks, failure modes, and edge cases that may not be handled.\n"
        "- Weaknesses or gaps in the proposed approach.\n"
        "- Assumptions that may not hold and the consequences if they break.\n"
        "- Trade-offs, costs, complexity, and potential side effects.\n"
        "- Alternative or complementary approaches worth considering.\n\n"
        "Provide your critique as a clear, structured list of findings with actionable suggestions for improvement."
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


def _format_task_block(task_desc: str) -> str:
    """Format a task description as a labeled block for inclusion in a prompt.

    Args:
        task_desc: The task description to format.

    Returns:
        The formatted task block string.
    """
    return f"Task Description:\n{task_desc}"


def build_review_prompt(file_path: str, content: str, review_focus: str, severity_filter: str = 'all') -> str:
    """Build a prompt asking a model to critique a file's content against a stated review focus.

    Args:
        file_path: Path to the file being reviewed.
        content: The body of the file to review.
        review_focus: The aspect of the code to prioritise (e.g. ``"security"``,
            ``"performance"``, ``"design"``).
        severity_filter: Optional severity filter restricting the reported
            findings. Defaults to ``"all"`` (no restriction). When set to any
            other value, only findings at or above that severity are requested.

    Returns:
        The formatted review prompt string.
    """
    template = get_prompt_template("REVIEW")
    prompt = template.format(
        file_path=file_path,
        code=content,
        review_focus=review_focus,
    )
    if severity_filter and severity_filter != 'all':
        prompt += f"\n\nOnly report findings of severity: {severity_filter}."
    return prompt


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


def build_critic_prompt(task_desc: str) -> str:
    """Build a critic-role gate prompt that critiques risks and weaknesses of a proposed approach.

    Args:
        task_desc: Description of the task whose proposed approach should be
            critiqued.

    Returns:
        The formatted critic prompt string.
    """
    template = get_prompt_template("CRITIC")
    return template.format(task_desc=_format_task_block(task_desc))
