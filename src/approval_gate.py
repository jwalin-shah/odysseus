def format_cli_confirmation_prompt(request: dict) -> str:
    kind = request.get('kind', '')
    summary = request.get('summary', '')
    owner = request.get('owner', '')

    if kind == 'write':
        header = f"Pending write action: {summary}"
        if owner:
            header += f" (owner: {owner})"
    elif kind == 'read':
        header = f"Allow read action: {summary}"
    else:
        header = f"Pending action: {summary}"
        if owner:
            header += f" (owner: {owner})"

    prompt = (
        f"{header}\n"
        f"This operation may modify resources. Confirm? [y/N/always/never]: "
    )
    return prompt
