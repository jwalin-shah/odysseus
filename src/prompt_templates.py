def build_improve_file_prompt(file_path: str, current_content: str, goal: str) -> str:
    """Build the IMPROVE_FILE prompt template.

    Constructs a prompt that asks the model to improve the contents of a file
    at ``file_path`` so that it better satisfies a stated ``goal``.

    Parameters
    ----------
    file_path:
        Path of the file being improved (included in the prompt for context).
    current_content:
        The current text content of the file.
    goal:
        A natural-language description of the desired improvement.

    Returns
    -------
    str
        A fully formatted prompt string ready to be sent to a language model.
    """
    prompt = (
        "You are a careful, expert software engineer.\n"
        "Your task is to improve the file described below so that it better "
        "achieves the stated goal.\n\n"
        "GOAL\n"
        "----\n"
        f"{goal}\n\n"
        "FILE PATH\n"
        "---------\n"
        f"{file_path}\n\n"
        "CURRENT CONTENT\n"
        "---------------\n"
        f"{current_content}\n\n"
        "INSTRUCTIONS\n"
        "------------\n"
        "- Read the current content and the goal carefully.\n"
        "- Rewrite the file so that it accomplishes the goal while preserving "
        "correct, production-quality code.\n"
        "- Keep the public interface and behavior intact unless the goal "
        "explicitly requires changing them.\n"
        "- Do not add unrelated refactors, comments, or dependencies.\n"
        "- Return ONLY the full, improved contents of the file. Do not wrap "
        "the output in a fenced code block, and do not include any additional "
        "explanatory text before or after the file contents.\n"
    )
    return prompt
