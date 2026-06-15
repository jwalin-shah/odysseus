def entry_input_tokens(entry: dict) -> int:
    return entry.get('input_tokens', entry.get('prompt_tokens', 0))
