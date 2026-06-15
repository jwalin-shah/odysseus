TEMPLATES = {
    "REVIEW": "Please review the following file: {target}",
    "EXPLAIN": "Explain the following code: {target}",
    "REFACTOR": "Refactor the following file: {target}",
}


def render_template(name: str, **kwargs: str) -> str:
    template = TEMPLATES[name]
    return template.format(**kwargs)
