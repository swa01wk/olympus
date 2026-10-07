from __future__ import annotations

import pytest
from core.domain.canonical_json import sha256_hex
from core.domain.enums import WorkType
from core.domain.task_contracts.schemas import TaskContractBody
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def test_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        TaskContractBody.model_validate(
            {
                "objective": "x",
                "work_type": "ANALYSIS",
                "inputs": [],
                "executor_kind": "DETERMINISTIC",
                "unexpected": True,
            }
        )


def test_frozen_body() -> None:
    body = TaskContractBody(
        objective="x",
        work_type=WorkType.ANALYSIS,
        inputs=[],
        executor_kind="DETERMINISTIC",
    )
    with pytest.raises(ValidationError):
        body.objective = "y"  # type: ignore[misc]


def test_hash_stable_across_key_order() -> None:
    a = {
        "objective": "o",
        "work_type": "CODE_CHANGE",
        "inputs": [],
        "executor_kind": "AGENT_RUNTIME",
    }
    b = {
        "executor_kind": "AGENT_RUNTIME",
        "inputs": [],
        "work_type": "CODE_CHANGE",
        "objective": "o",
    }
    assert sha256_hex(a) == sha256_hex(b)
