from dataclasses import dataclass


@dataclass
class PromptTemplate:
    name: str
    user: str
    system: str = ""
    assistant: str = ""


def search_replace_template() -> PromptTemplate:
    """Returns the SEARCH_REPLACE PromptTemplate that asks the model to emit
    exact search/replace pairs for a given file."""
    user_template = (
        "You are a code-editing assistant. Given the current content of a "
        "file, emit exact search/replace pairs to apply the requested change.\n\n"
        "Use the following format for each pair:\n"
        "search_text: {search_text}\n"
        "replace_text: {replace_text}\n\n"
        "Emit the search/replace pair for the following file:\n"
        "{file_content}\n"
    )
    return PromptTemplate(
        name="SEARCH_REPLACE",
        user=user_template,
        system=(
            "You are a meticulous code-editing assistant. When given a file's "
            "contents and a requested change, respond with exact search/replace "
            "pairs using the specified format. Do not include any additional "
            "text or commentary."
        ),
    )
