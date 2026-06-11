import json

def get_schemas():
    import importlib.util
    import sys
    # Avoid circular import by mocking or importing carefully
    import src.agent_tools
    from src.tool_schemas import FUNCTION_TOOL_SCHEMAS
    return FUNCTION_TOOL_SCHEMAS

# Let's just run pytest to see if it even runs:
