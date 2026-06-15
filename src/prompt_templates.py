def build_implement_fn_prompt(fn_signature: str, docstring: str, constraints: list[str]) -> str:
    """Build the IMPLEMENT_FN prompt template.

    Constructs a prompt instructing the model to implement a function
    given its signature, docstring, and a list of constraints.
    """
    constraints_section = ""
    if constraints:
        formatted_constraints = "\n".join(f"- {c}" for c in constraints)
        constraints_section = (
            "\n\nConstraints:\n"
            f"{formatted_constraints}"
        )

    prompt = (
        "You are an expert Python developer. Your task is to implement "
        "the following function according to its signature, docstring, "
        "and any provided constraints.\n\n"
        "Function signature:\n"
        f"{fn_signature}\n\n"
        "Docstring:\n"
        f"{docstring}"
        f"{constraints_section}\n\n"
        "Requirements:\n"
        "1. Implement the function body so that it satisfies the docstring.\n"
        "2. Adhere strictly to all stated constraints.\n"
        "3. Use only the Python standard library unless a constraint says otherwise.\n"
        "4. Return ONLY the complete function definition (including the "
        "signature line) with no additional commentary, explanation, or "
        "markdown formatting.\n\n"
        "Implementation:"
    )
    return prompt
