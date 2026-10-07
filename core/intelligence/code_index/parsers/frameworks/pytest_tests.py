from __future__ import annotations

import ast

from core.intelligence.code_index.build.types import DraftEntity, DraftRelation, ParsedModule
from core.intelligence.code_index.enums import EntityType, RelationType
from core.intelligence.code_index.parsers.imports import entity_key_for_qn


def extract_tests(
    module: ParsedModule,
    *,
    known_entities: set[str],
    route_paths: dict[str, str],
) -> tuple[list[DraftEntity], list[DraftRelation]]:
    entities: list[DraftEntity] = []
    relations: list[DraftRelation] = []
    if module.tree is None:
        return entities, relations

    def add_test(fn_name: str, qn: str, start: int, end: int) -> str:
        key = entity_key_for_qn(EntityType.TEST.value, module.file_path, qn)
        entities.append(
            DraftEntity(
                stable_key=key,
                type=EntityType.TEST,
                qualified_name=qn,
                file_path=module.file_path,
                start_line=start,
                end_line=end,
                is_public=True,
                metadata={"name": fn_name},
            )
        )
        return key

    for node in module.tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test_"
        ):
            qn = f"{module.module_name}.{node.name}"
            test_key = add_test(node.name, qn, node.lineno, node.end_lineno or node.lineno)
            _link_test_calls(node, test_key, module, known_entities, route_paths, relations)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(
                    item, ast.FunctionDef | ast.AsyncFunctionDef
                ) and item.name.startswith("test_"):
                    qn = f"{module.module_name}.{node.name}.{item.name}"
                    test_key = add_test(item.name, qn, item.lineno, item.end_lineno or item.lineno)
                    _link_test_calls(item, test_key, module, known_entities, route_paths, relations)

    return entities, relations


def _link_test_calls(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    test_key: str,
    module: ParsedModule,
    known_entities: set[str],
    route_paths: dict[str, str],
    relations: list[DraftRelation],
) -> None:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            http_attrs = {"get", "post", "put", "patch", "delete"}
            if (
                isinstance(sub.func, ast.Attribute)
                and sub.func.attr in http_attrs
                and sub.args
                and isinstance(sub.args[0], ast.Constant)
                and isinstance(sub.args[0].value, str)
            ):
                path = sub.args[0].value
                method = sub.func.attr.upper()
                route_key = f"ROUTE:{method} {path}"
                if route_key in known_entities:
                    relations.append(
                        DraftRelation(
                            source_key=route_key,
                            target_key=test_key,
                            relation=RelationType.VERIFIED_BY,
                            provenance="FRAMEWORK:pytest",
                        )
                    )
            target = _call_target_key(sub, module, known_entities)
            if target:
                relations.append(
                    DraftRelation(
                        source_key=target,
                        target_key=test_key,
                        relation=RelationType.VERIFIED_BY,
                        provenance="FRAMEWORK:pytest",
                    )
                )


def _call_target_key(call: ast.Call, module: ParsedModule, known: set[str]) -> str | None:
    if isinstance(call.func, ast.Name):
        qn = f"{module.module_name}.{call.func.id}"
        for et in (EntityType.FUNCTION, EntityType.METHOD, EntityType.CLASS):
            key = entity_key_for_qn(et.value, module.file_path, qn)
            if key in known:
                return key
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        qn = f"{module.module_name}.{call.func.value.id}.{call.func.attr}"
        key = entity_key_for_qn(EntityType.METHOD.value, module.file_path, qn)
        if key in known:
            return key
    return None


def match_route_literal(method: str, path: str) -> str:
    return f"ROUTE:{method.upper()} {path}"
