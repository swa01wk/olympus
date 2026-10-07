from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from core.intelligence.code_index.build.types import DraftEntity, DraftRelation, ParsedModule
from core.intelligence.code_index.enums import EntityType, RelationType
from core.intelligence.code_index.parsers.imports import entity_key_for_qn
from core.intelligence.code_index.stable_keys import entity_stable_key

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})


@dataclass
class RouterInfo:
    var_name: str
    prefix: str


def _str_constant(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_routes(
    module: ParsedModule,
    *,
    known_entities: set[str],
) -> tuple[list[DraftEntity], list[DraftRelation], dict[str, str]]:
    entities: list[DraftEntity] = []
    relations: list[DraftRelation] = []
    handler_to_route: dict[str, str] = {}
    if module.tree is None:
        return entities, relations, handler_to_route

    routers: dict[str, RouterInfo] = {}
    include_prefixes: dict[str, str] = {}

    for node in module.tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "APIRouter"
        ):
            prefix = ""
            for kw in node.value.keywords:
                if kw.arg == "prefix":
                    prefix = _str_constant(kw.value) or ""
            for target in node.targets:
                if isinstance(target, ast.Name):
                    routers[target.id] = RouterInfo(target.id, prefix or "")
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "include_router":
                router_ref = ""
                prefix = ""
                if call.args and isinstance(call.args[0], ast.Name):
                    router_ref = call.args[0].id
                for kw in call.keywords:
                    if kw.arg == "prefix":
                        prefix = _str_constant(kw.value) or ""
                if router_ref:
                    include_prefixes[router_ref] = prefix

    def route_prefix_for(decorators: list[ast.expr]) -> tuple[str, str, str | None]:
        for dec in decorators:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            method = None
            path = ""
            router_var = None
            if isinstance(func, ast.Attribute) and func.attr in HTTP_METHODS:
                method = func.attr.upper()
                if isinstance(func.value, ast.Name):
                    router_var = func.value.id
                if dec.args:
                    path = _str_constant(dec.args[0]) or ""
            if method:
                base = ""
                if router_var == "router" or router_var in routers:
                    info = routers.get(router_var or "router")
                    if info:
                        base = info.prefix
                elif router_var == "app":
                    base = ""
                extra = include_prefixes.get(router_var or "", "")
                full = _join_paths(base, extra, path)
                return method, full, router_var
        return "", "", None

    for fn in module.functions:
        if fn.body_node is None:
            continue
        method, path, _ = route_prefix_for(fn.body_node.decorator_list)
        if not method:
            continue
        stable = entity_stable_key(
            EntityType.ROUTE,
            file_path=module.file_path,
            qualified_name=fn.qualified_name,
            route_method=method,
            route_path=path,
        )
        handler_key = entity_key_for_qn(
            EntityType.FUNCTION.value, module.file_path, fn.qualified_name
        )
        entities.append(
            DraftEntity(
                stable_key=stable,
                type=EntityType.ROUTE,
                qualified_name=f"{method} {path}",
                file_path=module.file_path,
                start_line=fn.start_line,
                end_line=fn.end_line,
                is_public=True,
                metadata={"method": method, "path": path, "handler": fn.qualified_name},
            )
        )
        if handler_key in known_entities:
            relations.append(
                DraftRelation(
                    source_key=stable,
                    target_key=handler_key,
                    relation=RelationType.EXPOSES,
                    provenance="FRAMEWORK:fastapi",
                )
            )
        handler_to_route[handler_key] = stable

    return entities, relations, handler_to_route


def _join_paths(*parts: str) -> str:
    joined = "/".join(p.strip("/") for p in parts if p)
    if not joined.startswith("/"):
        joined = "/" + joined
    return re.sub(r"/+", "/", joined) or "/"
