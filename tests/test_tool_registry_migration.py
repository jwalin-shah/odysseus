import pytest
import src.agent_tools
from src.tool_schemas import FUNCTION_TOOL_SCHEMAS
from src.tool_registry import registry

def test_tool_registry_parity():
    """
    STRANGLER FIG MIGRATION TEST:
    This test ensures that as we migrate tools from the 4000-line monolith
    into the new @odysseus_tool registry, we do not drop or mutate any schemas.
    
    Currently, this will only check tools that have been migrated.
    Eventually, when all tools are migrated, we will assert exact length and content parity.
    """
    new_schemas = registry.get_all_schemas()
    new_names = {s["function"]["name"] for s in new_schemas}
    
    old_schemas_dict = {s["function"]["name"]: s for s in FUNCTION_TOOL_SCHEMAS}
    
    # 1. Ensure every schema migrated matches the old schema EXACTLY byte-for-byte (or key-for-key).
    for name in new_names:
        assert name in old_schemas_dict, f"Migrated tool {name} does not exist in old schemas!"
        assert old_schemas_dict[name] == next(s for s in new_schemas if s["function"]["name"] == name), f"Schema mismatch for {name}!"
        
    print(f"Migration Progress: {len(new_schemas)} / {len(FUNCTION_TOOL_SCHEMAS)} tools migrated.")
