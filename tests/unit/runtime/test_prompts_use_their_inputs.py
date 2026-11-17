"""A value a profile renders into a prompt is invisible to the model unless the template has a
slot for it; that silently left Warden reviewing nothing and Sentinel guessing obligations."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
_CALL = re.compile(
    r'load_prompt\("([^"]+)"\)(?:.*?)render_prompt\(\s*template,\s*(\{.*?\})\s*,?\s*\)', re.S
)


def _cases() -> list[tuple[str, str]]:
    out = []
    for f in sorted((ROOT / "core/runtime/profiles").glob("*.py")):
        for m in _CALL.finditer(f.read_text()):
            out.append((m.group(1), m.group(2)))
    return out


@pytest.mark.unit
@pytest.mark.parametrize(("prompt", "variables"), _cases())
def test_every_rendered_variable_has_a_slot(prompt: str, variables: str) -> None:
    keys = set(re.findall(r'"(\w+)":', variables))
    text = (ROOT / prompt).read_text()
    slots = set(re.findall(r"\{\{\s*(\w+)", text)) | set(re.findall(r"\{%\s*if\s+(\w+)", text))
    assert keys <= slots, f"{prompt} never shows {sorted(keys - slots)}"
