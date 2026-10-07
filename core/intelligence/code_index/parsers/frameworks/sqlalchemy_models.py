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
from core.intelligence.code_index.stable_keys import entity_stable_key


def _table_name(class_node: ast.ClassDef) -> str | None:
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__tablename__"
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    return node.value.value
    return None


def _is_orm_class(cls: ParsedClass) -> bool:
    if cls.node is None:
        return False
    if _table_name(cls.node):
        return True
    for base in cls.bases:
        if any(x in base for x in ("Base", "DeclarativeBase")):
            return _table_name(cls.node) is not None
    return False


def extract_models(
    module: ParsedModule,
) -> tuple[list[DraftEntity], list[DraftRelation]]:
    entities: list[DraftEntity] = []
    relations: list[DraftRelation] = []
    for cls in module.classes:
        if cls.node is None or not _is_orm_class(cls):
            continue
        table = _table_name(cls.node)
        model_key = entity_key_for_qn(
            EntityType.ORM_MODEL.value, module.file_path, cls.qualified_name
        )
        columns: list[dict[str, str]] = []
        for node in cls.node.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                columns.append({"name": node.target.id, "type": ast.unparse(node.annotation)})
        entities.append(
            DraftEntity(
                stable_key=model_key,
                type=EntityType.ORM_MODEL,
                qualified_name=cls.qualified_name,
                file_path=module.file_path,
                start_line=cls.start_line,
                end_line=cls.end_line,
                is_public=cls.is_public,
                metadata={"columns": columns, "table": table},
            )
        )
        if table:
            table_key = entity_stable_key(
                EntityType.TABLE, file_path=None, qualified_name=table, table_name=table
            )
            entities.append(
                DraftEntity(
                    stable_key=table_key,
                    type=EntityType.TABLE,
                    qualified_name=table,
                    file_path=None,
                    metadata={"name": table},
                )
            )
            relations.append(
                DraftRelation(
                    source_key=model_key,
                    target_key=table_key,
                    relation=RelationType.MAPS_TO,
                    provenance="FRAMEWORK:sqlalchemy",
                )
            )
    return entities, relations


def extract_accesses(
    module: ParsedModule,
    *,
    known_entities: set[str],
) -> list[DraftRelation]:
    relations: list[DraftRelation] = []
    if module.tree is None:
        return relations

    for node in ast.walk(module.tree):
        fn_qn = None
        file_path = module.file_path
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            fn_qn = f"{module.module_name}.{node.name}"
            fn_key = entity_key_for_qn(EntityType.FUNCTION.value, file_path, fn_qn)
            if fn_key not in known_entities:
                fn_key = entity_key_for_qn(EntityType.METHOD.value, file_path, fn_qn)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    model_name = _model_from_call(sub)
                    if model_name:
                        model_key = _find_model_key(model_name, module, known_entities)
                        if model_key:
                            relations.append(
                                DraftRelation(
                                    source_key=fn_key,
                                    target_key=model_key,
                                    relation=RelationType.ACCESSES,
                                    provenance="FRAMEWORK:sqlalchemy",
                                )
                            )
    return relations


def _model_from_call(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        if call.func.attr in {"query", "add", "get", "execute"}:
            if call.args and isinstance(call.args[0], ast.Name):
                return call.args[0].id
            if (
                call.args
                and isinstance(call.args[0], ast.Call)
                and isinstance(call.args[0].func, ast.Name)
            ):
                return call.args[0].func.id
        if call.func.attr == "execute" and call.args:
            arg = call.args[0]
            if (
                isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Name)
                and arg.func.id == "select"
                and arg.args
                and isinstance(arg.args[0], ast.Name)
            ):
                return arg.args[0].id
    return None


def _find_model_key(name: str, module: ParsedModule, known: set[str]) -> str | None:
    for cls in module.classes:
        if cls.name == name:
            key = entity_key_for_qn(
                EntityType.ORM_MODEL.value, module.file_path, cls.qualified_name
            )
            if key in known:
                return key
    for key in known:
        if key.endswith(f":{name}") and key.startswith("ORM_MODEL:"):
            return key
    return None
