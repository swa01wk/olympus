from __future__ import annotations

from core.intelligence.code_index.enums import EntityType


def entity_stable_key(
    entity_type: EntityType,
    *,
    file_path: str | None,
    qualified_name: str,
    route_method: str | None = None,
    route_path: str | None = None,
    table_name: str | None = None,
) -> str:
    if entity_type == EntityType.ROUTE:
        assert route_method and route_path
        return f"ROUTE:{route_method.upper()} {route_path}"
    if entity_type == EntityType.TABLE:
        assert table_name
        return f"TABLE:{table_name}"
    path = file_path or ""
    return f"{entity_type.value}:{path}:{qualified_name}"
