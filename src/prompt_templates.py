"""Prompt template registry.

Exposes a name-keyed registry mapping each supported prompt template
identifier to its zero-argument factory function. Each factory returns
a fresh PromptTemplate instance identified by its name.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class PromptTemplate:
    """A named prompt template."""

    name: str
    description: str = ""
    body: str = ""


def _factory(name: str) -> Callable[[], PromptTemplate]:
    """Build a zero-argument factory that produces a PromptTemplate with the given name."""

    def _build() -> PromptTemplate:
        return PromptTemplate(name=name)

    _build.__name__ = f"make_{name.lower()}"
    return _build


def list_templates() -> dict[str, Callable[[], PromptTemplate]]:
    """Return a name-keyed registry of supported template factory functions."""
    return {
        "IMPLEMENT_FN": _factory("IMPLEMENT_FN"),
        "IMPROVE_FILE": _factory("IMPROVE_FILE"),
        "REVIEW": _factory("REVIEW"),
        "SEARCH_REPLACE": _factory("SEARCH_REPLACE"),
    }
