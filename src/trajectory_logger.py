def extract_tool_pairs(messages: list[dict]) -> list[tuple[dict, dict]]:
    """
    Extract ordered (assistant_tool_call_message, tool_result_message) pairs
    from a list of chat messages, matched by tool_call_id.

    Args:
        messages: A list of message dictionaries. Each message has a 'role' key.
            Assistant messages with tool calls have a 'tool_calls' list, where each
            tool call has an 'id'. Tool result messages have a 'role' of 'tool'
            and a 'tool_call_id' that matches the id of a tool call.

    Returns:
        A list of tuples, each tuple containing (assistant_message, tool_result_message).
        Only pairs where a matching tool result exists are included.
    """
    # First pass: collect tool result messages by their tool_call_id
    tool_messages = {}
    for msg in messages:
        if msg.get('role') == 'tool':
            tool_call_id = msg.get('tool_call_id')
            if tool_call_id is not None and tool_call_id not in tool_messages:
                tool_messages[tool_call_id] = msg

    # Second pass: iterate through assistant messages and create pairs
    pairs = []
    for msg in messages:
        if msg.get('role') == 'assistant':
            tool_calls = msg.get('tool_calls')
            if tool_calls:
                for call in tool_calls:
                    call_id = call.get('id')
                    if call_id in tool_messages:
                        pairs.append((msg, tool_messages[call_id]))

    return pairs
