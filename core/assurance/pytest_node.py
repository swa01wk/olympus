"""Map code-index TEST entities and junit cases to pytest node ids."""

from __future__ import annotations

from pathlib import Path

from core.intelligence.code_index.models import CodeEntity


def pytest_node_id_for_entity(entity: CodeEntity) -> str | None:
    name = (entity.entity_metadata or {}).get("name")
    if entity.file_path and name:
        return f"{entity.file_path}::{name}"
    return entity.qualified_name


def junit_case_node_id(workspace: Path, classname: str, name: str) -> str:
    """Turn a junit ``classname``/``name`` pair into a runnable pytest node id.

    Pytest writes ``classname`` as a dotted module path plus any test classes
    (``tests.test_api.TestX``); the longest prefix that is a file in ``workspace``
    is the module, the rest are class segments.
    """
    parts = [p for p in classname.split(".") if p]
    for cut in range(len(parts), 0, -1):
        rel = "/".join(parts[:cut]) + ".py"
        if (workspace / rel).is_file():
            return "::".join([rel, *parts[cut:], name])
    return f"{classname}::{name}" if classname else name


def legacy_node_to_path(workspace: Path, node: str) -> str:
    """Rewrite a ``dotted.module::test`` ref recorded before path-form node ids."""
    head, sep, tail = node.partition("::")
    if not sep or head.endswith(".py") or "/" in head:
        return node
    converted = junit_case_node_id(workspace, head, tail)
    return converted if converted.split("::", 1)[0].endswith(".py") else node
