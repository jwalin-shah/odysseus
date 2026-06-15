from dataclasses import dataclass


@dataclass
class PromptTemplate:
    name: str
    body: str


def build_implement_fn_template() -> PromptTemplate:
    body = (
        "You are an expert Python developer. Your task is to implement a new "
        "function based on the provided signature and docstring.\n\n"
        "Function signature:\n{signature}\n\n"
        "Docstring:\n{docstring}\n\n"
        "Requirements:\n"
        "1. Implement the function so that it fully satisfies the behavior "
        "described in the docstring.\n"
        "2. Include any necessary import statements at the top of the code.\n"
        "3. Follow PEP 8 style guidelines and write clean, readable, well-"
        "documented code.\n"
        "4. Handle edge cases and invalid inputs gracefully where appropriate.\n"
        "5. Return only the complete, runnable function implementation without "
        "any additional explanations, markdown formatting, or code fences."
    )
    return PromptTemplate(name="IMPLEMENT_FN", body=body)
