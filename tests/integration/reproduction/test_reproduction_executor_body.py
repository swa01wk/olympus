"""Contract body parsing for reproduction.run (executor extensions)."""

from __future__ import annotations

import uuid

from core.domain.enums import WorkType
from core.domain.task_contracts.schemas import TaskContractBody, parse_task_contract_body


def test_parse_reproduction_run_contract_strips_executor_fields() -> None:
    repo_id = uuid.uuid4()
    defect_id = uuid.uuid4()
    raw = {
        **TaskContractBody(
            objective="run repro",
            work_type=WorkType.VERIFICATION,
            inputs=[],
            repository_id=repo_id,
            executor_kind="DETERMINISTIC",
            deterministic_executor="reproduction.run",
            required_outputs=[],
        ).model_dump(mode="json"),
        "defect_id": str(defect_id),
        "phase": "PRE_REPAIR",
        "artifact_id": str(uuid.uuid4()),
        "commit_sha": "abc123",
        "observed_symptom_signature": {"kind": "http_status", "value": 500},
        "stability_runs": 2,
    }
    parsed = parse_task_contract_body(raw)
    assert parsed.deterministic_executor == "reproduction.run"
    assert parsed.required_outputs == []
