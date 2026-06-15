from string import Template

TEMPLATES = {
    "IMPLEMENT_FN": """Implement the following Python function:

{signature}

Function specification: {spec}

Provide a complete, working implementation with appropriate error handling and a docstring.""",
    "SEARCH_REPLACE": """Apply the following search and replace operation in the file {file_path}:

Search for:
{search_text}

Replace with:
{replace_text}"""
}


def render_template(name: str, **kwargs) -> str:
    template = TEMPLATES.get(name)
    if template is None:
        return ""
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
