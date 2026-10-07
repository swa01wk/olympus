"""Principal-symbol rule for GENERATED_LINEAGE links."""

from __future__ import annotations

from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.models import CodeEntity

_PRINCIPAL_TYPES = frozenset(
    {
        EntityType.ROUTE,
        EntityType.CLASS,
        EntityType.ORM_MODEL,
        EntityType.SCHEMA,
        EntityType.TABLE,
        EntityType.FUNCTION,
        EntityType.METHOD,
    }
)


def is_principal_entity(entity: CodeEntity, declared_symbols: set[str]) -> bool:
    if entity.type not in _PRINCIPAL_TYPES:
        return False
    if entity.type == EntityType.FUNCTION:
        if not entity.is_public:
            return False
        short = entity.qualified_name.split(".")[-1]
        return not short.startswith("_")
    if entity.type == EntityType.METHOD:
        parts = entity.qualified_name.rsplit(".", 1)
        if len(parts) != 2:
            return False
        method_name = parts[1]
        if method_name.startswith("_"):
            return False
        return method_name in declared_symbols or entity.qualified_name in declared_symbols
    if entity.type in {EntityType.ROUTE, EntityType.ORM_MODEL, EntityType.SCHEMA, EntityType.TABLE}:
        return True
    return bool(entity.type == EntityType.CLASS and entity.is_public)
