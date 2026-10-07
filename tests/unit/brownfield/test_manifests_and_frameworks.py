from __future__ import annotations

from core.intelligence.repository.frameworks import detect_frameworks
from core.intelligence.repository.manifests import parse_pyproject, parse_requirements


def test_parse_pyproject_dependencies() -> None:
    text = """
[project]
name = "demo"
dependencies = ["fastapi>=0.1", "sqlalchemy==2.0.0"]
"""
    parsed = parse_pyproject(text, "pyproject.toml")
    assert parsed.name == "demo"
    deps = parsed.dependencies
    assert ("fastapi", None) in deps or any(d[0] == "fastapi" for d in deps)


def test_parse_requirements() -> None:
    parsed = parse_requirements("pytest==8.0\nfastapi\n", "requirements.txt")
    names = {d[0] for d in parsed.dependencies}
    assert "pytest" in names
    assert "fastapi" in names


def test_detect_frameworks() -> None:
    found = detect_frameworks(
        [("fastapi", None), ("pytest", "8")],
        ["fastapi", "sqlalchemy.orm"],
        "from fastapi import FastAPI",
    )
    assert "fastapi" in found
    assert "sqlalchemy" in found
    assert "pytest" in found
