from dataclasses import dataclass


@dataclass
class PromptTemplate:
    name: str
    body: str


def build_review_template() -> PromptTemplate:
    body = (
        "You are an expert code reviewer. Perform a structured code review of the "
        "following {language} code diff and organize your findings into clear categories.\n\n"
        "Review Categories:\n"
        "1. Bugs: Correctness issues that would cause incorrect behavior.\n"
        "2. Security: Potential security vulnerabilities or unsafe practices.\n"
        "3. Performance: Performance concerns, inefficiencies, or optimization opportunities.\n"
        "4. Style: Style, formatting, naming, or convention issues.\n"
        "5. Best Practices: Deviations from established best practices or maintainability concerns.\n"
        "6. Tests: Suggestions for test coverage or test improvements.\n\n"
        "Instructions:\n"
        "- For each finding, specify the category, file/line (if applicable), and a concise description.\n"
        "- If a category has no findings, omit it.\n"
        "- Be specific, actionable, and constructive.\n"
        "- Do not modify the code yourself; only report findings.\n\n"
        "Language: {language}\n\n"
        "Diff:\n"
        "{diff}\n\n"
        "Structured Review:"
    )
    return PromptTemplate(name="REVIEW", body=body)
