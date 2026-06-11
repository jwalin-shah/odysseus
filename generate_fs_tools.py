import json
import os
import sys

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(".")))
from src.tool_schemas import FUNCTION_TOOL_SCHEMAS

tools_to_extract = ["read_file", "grep", "glob", "ls", "write_file", "edit_file", "create_document", "edit_document", "suggest_document", "update_document"]

with open("src/tools/filesystem_tools.py", "w") as f:
    f.write("from typing import Dict, Any, Optional\n")
    f.write("from src.tool_registry import odysseus_tool\n")
    f.write("from src.tool_implementations import (\n")
    f.write("    do_create_document,\n")
    f.write("    do_update_document,\n")
    f.write("    do_edit_document,\n")
    f.write("    do_suggest_document,\n")
    f.write(")\n")
    f.write("from src.tool_execution import _do_edit_file\n\n")

    for tool_name in tools_to_extract:
        schema = next(s for s in FUNCTION_TOOL_SCHEMAS if s["function"]["name"] == tool_name)
        schema_var = f"{tool_name.upper()}_SCHEMA"
        f.write(f"{schema_var} = {json.dumps(schema, indent=4)}\n\n")

        # For implementations, we can write a stub that redirects, or actual implementations.
        if tool_name == "create_document":
            f.write(f"@odysseus_tool({schema_var})\n")
            f.write(f"async def {tool_name}(*args, **kwargs):\n")
            f.write(f"    return await do_create_document(*args, **kwargs)\n\n")
        elif tool_name == "update_document":
            f.write(f"@odysseus_tool({schema_var})\n")
            f.write(f"async def {tool_name}(*args, **kwargs):\n")
            f.write(f"    return await do_update_document(*args, **kwargs)\n\n")
        elif tool_name == "edit_document":
            f.write(f"@odysseus_tool({schema_var})\n")
            f.write(f"async def {tool_name}(*args, **kwargs):\n")
            f.write(f"    return await do_edit_document(*args, **kwargs)\n\n")
        elif tool_name == "suggest_document":
            f.write(f"@odysseus_tool({schema_var})\n")
            f.write(f"async def {tool_name}(*args, **kwargs):\n")
            f.write(f"    return await do_suggest_document(*args, **kwargs)\n\n")
        elif tool_name == "edit_file":
            f.write(f"@odysseus_tool({schema_var})\n")
            f.write(f"async def {tool_name}(*args, **kwargs):\n")
            f.write(f"    return await _do_edit_file(*args, **kwargs)\n\n")
        else:
            # Inline tools - just stubs for now since we are migrating schemas
            f.write(f"@odysseus_tool({schema_var})\n")
            f.write(f"async def {tool_name}(*args, **kwargs):\n")
            f.write(f"    pass # TODO: Extract from tool_execution.py in Phase 2\n\n")

print("Generated src/tools/filesystem_tools.py")
