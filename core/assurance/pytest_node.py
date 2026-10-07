"""Map code-index TEST entities to pytest node ids."""

from __future__ import annotations

from core.intelligence.code_index.models import CodeEntity


def pytest_node_id_for_entity(entity: CodeEntity) -> str | None:
    name = (entity.entity_metadata or {}).get("name")
    if entity.file_path and name:
        return f"{entity.file_path}::{name}"
    return entity.qualified_name
