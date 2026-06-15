from dataclasses import dataclass


@dataclass
class PromptTemplate:
    name: str
    system: str
    user: str


def improve_file_template() -> PromptTemplate:
    return PromptTemplate(
        name="IMPROVE_FILE",
        system=(
            "You are an expert software engineer and code reviewer. "
            "Your task is to analyze the provided file and suggest concrete, "
            "actionable improvements. Focus on correctness, readability, "
            "performance, maintainability, security, and adherence to "
            "project conventions. Provide a brief rationale for each "
            "suggestion and, when appropriate, include code examples."
        ),
        user=(
            "Please review and suggest improvements for the file at {file_path}.\n"
            "Here are the current contents of the file:\n\n"
            "{file_contents}\n\n"
            "Provide your suggestions in a clear, organized list."
        ),
    )
