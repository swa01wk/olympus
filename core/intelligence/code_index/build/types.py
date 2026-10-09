from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.intelligence.code_index.enums import EntityType, RelationType


@dataclass
class DraftEntity:
    stable_key: str
    type: EntityType
    qualified_name: str
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    content_hash: str = ""
    is_public: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DraftRelation:
    source_key: str
    target_key: str
    relation: RelationType
    provenance: str
    confidence: float = 1.0


@dataclass
class ParsedFunction:
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    is_method: bool
    class_name: str | None
    decorators: list[str]
    signature: str
    doc_first_line: str | None
    is_public: bool
    body_node: Any = None


@dataclass
class ParsedClass:
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    bases: list[str]
    decorators: list[str]
    doc_first_line: str | None
    is_public: bool
    methods: list[ParsedFunction] = field(default_factory=list)
    node: Any = None


@dataclass
class ParsedModule:
    file_path: str
    module_name: str
    source: str
    tree: Any
    functions: list[ParsedFunction]
    classes: list[ParsedClass]
    parse_error: str | None = None
