from __future__ import annotations

import ast

from core.intelligence.code_index.build.types import (
    DraftEntity,
    DraftRelation,
    ParsedClass,
    ParsedModule,
)
from core.intelligence.code_index.enums import EntityType, RelationType
from core.intelligence.code_index.parsers.imports import entity_key_for_qn


def _is_basemodel_class(cls: ParsedClass) -> bool:
    return any("BaseModel" in base for base in cls.bases)


def _is_str_enum_class(cls: ParsedClass) -> bool:
    return any("StrEnum" in base or base.endswith("Enum") for base in cls.bases)


def _field_info(class_node: ast.ClassDef) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    for node in class_node.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            fields.append({"name": node.target.id, "type": ast.unparse(node.annotation)})
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    fields.append({"name": target.id, "type": ""})
    return fields


def extract_schemas(
    module: ParsedModule,
    *,
    known_entities: set[str],
) -> tuple[list[DraftEntity], list[DraftRelation]]:
    entities: list[DraftEntity] = []
    relations: list[DraftRelation] = []
    for cls in module.classes:
        if not _is_basemodel_class(cls) and not _is_str_enum_class(cls):
            continue
        key = entity_key_for_qn(EntityType.SCHEMA.value, module.file_path, cls.qualified_name)
        meta: dict[str, object] = {"fields": []}
        if cls.node is not None:
            meta["fields"] = _field_info(cls.node)
        entities.append(
            DraftEntity(
                stable_key=key,
                type=EntityType.SCHEMA,
                qualified_name=cls.qualified_name,
                file_path=module.file_path,
                start_line=cls.start_line,
                end_line=cls.end_line,
                is_public=cls.is_public,
                metadata=meta,
            )
        )

    if module.tree is None:
        return entities, relations

    for node in ast.walk(module.tree):
        if isinstance(node, ast.FunctionDef):
            fn_key = entity_key_for_qn(
                EntityType.FUNCTION.value, module.file_path, f"{module.module_name}.{node.name}"
            )
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                if isinstance(dec.func, ast.Attribute) and dec.func.attr in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                }:
                    for kw in dec.keywords:
                        if kw.arg == "response_model" and isinstance(kw.value, ast.Name):
                            schema_key = entity_key_for_qn(
                                EntityType.SCHEMA.value,
                                module.file_path,
                                f"{module.module_name}.{kw.value.id}",
                            )
                            if schema_key not in known_entities:
                                for cls in module.classes:
                                    if cls.name == kw.value.id:
                                        schema_key = entity_key_for_qn(
                                            EntityType.SCHEMA.value,
                                            module.file_path,
                                            cls.qualified_name,
                                        )
                            if schema_key in known_entities or any(
                                e.stable_key == schema_key for e in entities
                            ):
                                relations.append(
                                    DraftRelation(
                                        source_key=fn_key,
                                        target_key=schema_key,
                                        relation=RelationType.USES_SCHEMA,
                                        provenance="FRAMEWORK:pydantic",
                                    )
                                )
    return entities, relations
