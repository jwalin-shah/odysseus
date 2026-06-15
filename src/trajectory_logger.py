def extract_assistant_turn(messages: list[dict]) -> dict:
    for message in reversed(messages):
        if message.get('role') == 'assistant':
            return message
    return {}
