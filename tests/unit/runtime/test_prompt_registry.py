from __future__ import annotations

import pytest
from core.runtime.prompts.registry import load_prompt, render_prompt
from jinja2.exceptions import UndefinedError

pytestmark = pytest.mark.unit


def test_prompt_hash_stable() -> None:
    first = load_prompt("core/runtime/prompts/diagnostic_structured_echo.md")
    second = load_prompt("core/runtime/prompts/diagnostic_structured_echo.md")
    assert first.content_hash == second.content_hash


def test_render_missing_variable_raises() -> None:
    template = load_prompt("core/runtime/prompts/diagnostic_structured_echo.md")
    with pytest.raises(UndefinedError):
        render_prompt(template, {})


def test_orchestrator_converse_prompt_has_id_and_version() -> None:
    template = load_prompt("agents/orchestrator/prompts/converse.md")
    assert template.template_id == "orchestrator.converse"
    assert template.version
