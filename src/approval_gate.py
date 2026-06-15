def read_cli_confirmation(prompt: str, default: bool = False, input_func=input) -> bool:
    response = input_func(prompt).strip()
    if not response:
        return default
    return response.lower().startswith('y')
