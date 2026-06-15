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
        "You are a critical reviewer. Carefully critique the following task and any proposed approach.\n\n"
        "Task:\n{task_desc}\n\n"
        "Identify weaknesses, risks, edge cases, and potential failure modes. Be specific and constructive."
    ),
    "VERIFIER": (
        "You are a meticulous verifier. Verify the following task and its proposed solution against the stated requirements.\n\n"
        "Task:\n{task_desc}\n\n"
        "Check for correctness, completeness, and adherence to the specification. Flag any deviations."
    ),
    "JUDGE": (
        "You are an impartial judge. Evaluate the following task and the proposed solution.\n\n"
        "Task:\n{task_desc}\n\n"
        "Provide a clear verdict with justification, weighing trade-offs and overall quality."
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
    """Build a prompt asking a model to critically review a task description.

    Args:
        task_desc: Description of the task to critique.

    Returns:
        The formatted critic prompt string.
    """
    template = get_prompt_template("CRITIC")
    return template.format(task_desc=task_desc)


def build_verifier_prompt(task_desc: str) -> str:
    """Build a prompt asking a model to verify a task description.

    Args:
        task_desc: Description of the task to verify.

    Returns:
        The formatted verifier prompt string.
    """
    template = get_prompt_template("VERIFIER")
    return template.format(task_desc=task_desc)


def build_judge_prompt(task_desc: str) -> str:
    """Build a prompt asking a model to judge a task description.

    Args:
        task_desc: Description of the task to judge.

    Returns:
        The formatted judge prompt string.
    """
    template = get_prompt_template("JUDGE")
    return template.format(task_desc=task_desc)


def build_gate_prompts(task_desc: str) -> dict:
    """Assemble the adaptive gate prompt set for a given task description.

    Args:
        task_desc: Description of the task being gated.

    Returns:
        A dictionary with keys ``'critic'``, ``'verifier'``, and ``'judge'``,
        each mapping to a formatted prompt string that embeds ``task_desc``.
    """
    return {
        'critic': build_critic_prompt(task_desc),
        'verifier': build_verifier_prompt(task_desc),
        'judge': build_judge_prompt(task_desc),
    }
