from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass

from core.intelligence.code_index.build.types import DraftRelation
from core.intelligence.code_index.enums import RelationType


@dataclass
class ImportBinding:
    local_name: str
    target_module: str | None
    target_entity_qn: str | None


@dataclass
class ImportAnalysis:
    bindings: dict[str, ImportBinding]
    external_imports: list[dict[str, str]]
    relations: list[DraftRelation]


def _top_level(name: str) -> str:
    return name.split(".", 1)[0]


def parse_declared_dependencies(manifests: dict[str, str]) -> set[str]:
    declared: set[str] = set()
    for path, text in manifests.items():
        if path.endswith("pyproject.toml"):
            for match in re.finditer(r'["\']([a-zA-Z0-9][\w.-]*)["\']\s*[,=]', text):
                declared.add(match.group(1).lower().replace("-", "_"))
            for match in re.finditer(r"name\s*=\s*[\"']([^\"']+)[\"']", text):
                declared.add(match.group(1).lower().replace("-", "_"))
        else:
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                pkg = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip()
                if pkg:
                    declared.add(pkg.lower().replace("-", "_"))
    return declared


def _distribution_map() -> dict[str, str]:
    try:
        from importlib.metadata import packages_distributions

        mapping: dict[str, str] = {}
        for dist, pkgs in packages_distributions().items():
            for pkg in pkgs:
                mapping[pkg] = dist
        return mapping
    except Exception:
        return {}


def classify_external(top: str, declared: set[str], dist_map: dict[str, str]) -> str:
    if top in sys.stdlib_module_names:
        return "STDLIB"
    norm = top.lower().replace("-", "_")
    if norm in declared:
        return "DECLARED_DEPENDENCY"
    if top in dist_map and dist_map[top].lower().replace("-", "_") in declared:
        return "DECLARED_DEPENDENCY"
    return "UNDECLARED"


def resolve_relative(module_name: str, level: int, module: str | None) -> str:
    if level == 0:
        return module or ""
    parts = module_name.split(".")
    if level > len(parts):
        base: list[str] = []
    else:
        base = parts[: len(parts) - level]
    if module:
        base.extend(module.split("."))
    return ".".join(p for p in base if p)


def analyze_imports(
    *,
    file_path: str,
    module_name: str,
    tree: ast.AST | None,
    module_index: dict[str, str],
    declared_deps: set[str],
    source_module_key: str,
) -> ImportAnalysis:
    bindings: dict[str, ImportBinding] = {}
    external: list[dict[str, str]] = []
    relations: list[DraftRelation] = []
    dist_map = _distribution_map()

    if tree is None:
        return ImportAnalysis(bindings=bindings, external_imports=external, relations=relations)

    def add_local_relation(target_module: str, provenance: str = "AST") -> None:
        target_path = module_index.get(target_module)
        if target_path is None:
            return
        target_key = f"MODULE:{target_path}:"
        relations.append(
            DraftRelation(
                source_key=source_module_key,
                target_key=target_key,
                relation=RelationType.IMPORTS,
                provenance=provenance,
            )
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                local = alias.asname or _top_level(name)
                bindings[local] = ImportBinding(
                    local_name=local, target_module=name, target_entity_qn=None
                )
                top = _top_level(name)
                if top in sys.stdlib_module_names or module_index.get(name) is None:
                    external.append(
                        {
                            "name": name,
                            "classification": classify_external(top, declared_deps, dist_map),
                        }
                    )
                else:
                    add_local_relation(name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None and node.level == 0:
                continue
            resolved = resolve_relative(module_name, node.level, node.module)
            for alias in node.names:
                if alias.name == "*":
                    bindings["*"] = ImportBinding("*", resolved, None)
                    add_local_relation(resolved)
                    continue
                local = alias.asname or alias.name
                target_qn = f"{resolved}.{alias.name}" if resolved else alias.name
                bindings[local] = ImportBinding(local, resolved, target_qn)
                top = _top_level(resolved)
                if module_index.get(resolved) is not None:
                    add_local_relation(resolved)
                else:
                    external.append(
                        {
                            "name": resolved,
                            "classification": classify_external(top, declared_deps, dist_map),
                        }
                    )

    return ImportAnalysis(bindings=bindings, external_imports=external, relations=relations)


def module_entity_key(file_path: str) -> str:
    return f"MODULE:{file_path}:"


def entity_key_for_qn(entity_type: str, file_path: str, qualified_name: str) -> str:
    return f"{entity_type}:{file_path}:{qualified_name}"
