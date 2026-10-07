from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from core.runtime.context import GraphDeps

GraphFactory = Callable[[GraphDeps], Any]


@dataclass(frozen=True)
class AgentProfile:
    name: str
    description: str
    model_alias: str
    prompt_templates: tuple[str, ...]
    output_schema: type[BaseModel] | None
    allowed_tools: tuple[str, ...]
    graph_factory: GraphFactory
    max_steps: int = 40


_REGISTRY: dict[str, AgentProfile] = {}


def register_profile(profile: AgentProfile) -> None:
    if profile.name in _REGISTRY:
        raise ValueError(f"Agent profile already registered: {profile.name}")
    _REGISTRY[profile.name] = profile


def get_profile(name: str) -> AgentProfile:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown agent profile: {name}")
    return _REGISTRY[name]


def all_profiles() -> dict[str, AgentProfile]:
    return dict(_REGISTRY)


def clear_profiles() -> None:
    _REGISTRY.clear()
