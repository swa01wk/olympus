from __future__ import annotations

import ast
import re


def extract_status_asserts(source: str) -> list[str]:
    tree = ast.parse(source)
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        text = ast.get_source_segment(source, node) or ""
        m = re.search(r"status_code\s*==\s*(\d+)", text)
        if m:
            out.append(m.group(1))
    return out


def test_status_code_assert_extraction() -> None:
    src = """
def test_x():
    assert resp.status_code == 201
    assert body["status"] == "OPEN"
"""
    assert "201" in extract_status_asserts(src)
