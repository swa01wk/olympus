from __future__ import annotations

from core.intelligence.code_index.build.types import DraftRelation, ParsedClass
from core.intelligence.code_index.enums import EntityType, RelationType
from core.intelligence.code_index.parsers.imports import entity_key_for_qn


def analyze_inheritance(
    *,
    file_path: str,
    cls: ParsedClass,
    module_index: dict[str, str],
    known_entities: set[str],
) -> list[DraftRelation]:
    relations: list[DraftRelation] = []
    source = entity_key_for_qn(EntityType.CLASS.value, file_path, cls.qualified_name)
    for base_expr in cls.bases:
        base_name = base_expr.split("(")[0].strip()
        if base_name in {"object", "BaseModel", "Base", "DeclarativeBase"}:
            continue
        candidates = [
            entity_key_for_qn(
                EntityType.CLASS.value,
                file_path,
                f"{cls.qualified_name.rsplit('.', 1)[0]}.{base_name}",
            ),
            entity_key_for_qn(EntityType.CLASS.value, file_path, base_name),
        ]
        for path in module_index.values():
            mod = path.replace("/", ".").removesuffix(".py")
            if mod.endswith("__init__"):
                mod = mod.rsplit(".", 1)[0]
            candidates.append(entity_key_for_qn(EntityType.CLASS.value, path, f"{mod}.{base_name}"))
        for key in candidates:
            if key in known_entities:
                relations.append(
                    DraftRelation(
                        source_key=source,
                        target_key=key,
                        relation=RelationType.INHERITS,
                        provenance="AST",
                    )
                )
                break
    return relations
