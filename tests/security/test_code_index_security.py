import ast
from pathlib import Path

import pytest
from core.intelligence.code_index.build.pipeline import build_index_from_sources

pytestmark = pytest.mark.security


def test_indexer_does_not_import_evil_module() -> None:
    evil = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "repos"
        / "indexer_edge_cases"
        / "evil.py"
    )
    source = evil.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert isinstance(tree, ast.Module)
    result = build_index_from_sources(
        repository_name="edge",
        commit_sha="0" * 40,
        py_sources={"evil.py": source},
        manifests={},
    )
    assert any(e.file_path == "evil.py" for e in result.entities)
    assert result.parse_errors == {}
