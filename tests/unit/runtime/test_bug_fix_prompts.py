"""Bug-fix agent prompts render with exactly the keys their profiles supply."""

from __future__ import annotations

import pytest
from core.runtime.prompts.registry import load_prompt, render_prompt

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("path", "values", "expected"),
    [
        (
            "agents/sentinel/prompts/reproduce.md",
            {
                "triage_json": '{"severity": "S2"}',
                "defect_description": "PATCH on CLOSED returns 500",
                "index_summary": "ROUTE PATCH /tickets/{ticket_id} (app/api/tickets.py)",
                "code_excerpt": "# --- app/main.py ---\napp = FastAPI()",
            },
            ["ROUTE PATCH /tickets/{ticket_id}", "# --- app/main.py ---", "got <status>"],
        ),
        (
            "agents/kira/prompts/expected_behavior.md",
            {
                "defect_description": "PATCH on CLOSED returns 500",
                "triage_json": "{}",
                "approved_acs_json": '[{"citation": "SPEC-FEAT-0002/AC-1"}]',
            },
            ["SPEC-FEAT-0002/AC-1", "Never cite a feature or spec key on its own"],
        ),
    ],
)
def test_bug_fix_prompt_renders(path: str, values: dict[str, str], expected: list[str]) -> None:
    rendered = render_prompt(load_prompt(path), {**values, "revision_feedback": ""})
    for text in expected:
        assert text in rendered
