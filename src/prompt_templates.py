from dataclasses import dataclass


@dataclass
class PromptTemplate:
    name: str
    system: str
    user: str


def review_template() -> PromptTemplate:
    system = (
        "You are an expert code reviewer. Perform a structured code review over "
        "the target file and any provided diff. Identify correctness issues, "
        "security vulnerabilities, performance problems, style violations, and "
        "suggest concrete improvements."
    )
    user = (
        "Please perform a structured code review.\n\n"
        "Target file:\n{target}\n\n"
        "Diff (if any):\n{diff}\n\n"
        "Provide your review in a structured format covering:\n"
        "1. Correctness\n"
        "2. Security\n"
        "3. Performance\n"
        "4. Style and Readability\n"
        "5. Suggested Changes"
    )
    return PromptTemplate(name="REVIEW", system=system, user=user)
