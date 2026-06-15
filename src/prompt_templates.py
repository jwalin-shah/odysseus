from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class PromptTemplate:
    name: str
    body: str


_REGISTRY: Dict[str, PromptTemplate] = {}


def register_template(template: PromptTemplate) -> None:
    """Register a PromptTemplate into the in-process template registry, keyed by its name, replacing any existing entry."""
    _REGISTRY[template.name] = template


def get_template(name: str) -> Optional[PromptTemplate]:
    """Retrieve a PromptTemplate by name from the in-process registry."""
    return _REGISTRY.get(name)
