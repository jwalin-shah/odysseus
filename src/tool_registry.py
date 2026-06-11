import logging
from typing import Callable, Dict, Any, List

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self.schemas: List[Dict[str, Any]] = []
        self.implementations: Dict[str, Callable] = {}
        self.name_map: Dict[str, str] = {}

    def register(self, schema: Dict[str, Any], aliases: List[str] = None):
        if aliases is None:
            aliases = []
            
        def decorator(func: Callable):
            tool_name = schema.get("function", {}).get("name")
            if not tool_name:
                raise ValueError("Schema must have a function.name")
                
            self.schemas.append(schema)
            self.implementations[tool_name] = func
            
            self.name_map[tool_name] = tool_name
            for alias in aliases:
                self.name_map[alias] = tool_name
                
            return func
        return decorator

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        return self.schemas

    def get_implementation(self, name: str) -> Callable:
        mapped_name = self.name_map.get(name, name)
        return self.implementations.get(mapped_name)

# Global singleton registry
registry = ToolRegistry()

def odysseus_tool(schema: Dict[str, Any], aliases: List[str] = None):
    """
    Decorator to register a tool schema and its implementation function.
    """
    return registry.register(schema, aliases)
import src.tools.filesystem_tools
import src.tools.email_tools
