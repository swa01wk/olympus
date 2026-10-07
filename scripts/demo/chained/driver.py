"""Chained MVP driver — HTTP client, pause/resume, reporting (Phase 19 §4.2)."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx


@dataclass
class ChainedDriverConfig:
    api_base: str
    human_token: str
    viewer_token: str | None = None
    pause_before: str | None = None
    chaos: bool = False
    report_dir: Path | None = None
    pause_file: Path = Path("var/olympus/demo/pause.json")
    dashboard_base: str = "http://127.0.0.1:3010"


@dataclass
class StageTiming:
    name: str
    started_at: datetime
    finished_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChainedRunReport:
    run_id: str
    chaos: bool
    project_id: str | None = None
    project_key: str = "SUPPORTDESK"
    stages: list[StageTiming] = field(default_factory=list)
    releases: dict[str, str] = field(default_factory=dict)
    cycles: dict[str, str] = field(default_factory=dict)
    llm_cost_usd: Decimal = Decimal("0")

    def start_stage(self, name: str) -> StageTiming:
        st = StageTiming(name=name, started_at=datetime.now(UTC))
        self.stages.append(st)
        return st

    def finish_stage(self, st: StageTiming, **metadata: Any) -> None:
        st.finished_at = datetime.now(UTC)
        st.metadata.update(metadata)

    def write(self, report_dir: Path) -> Path:
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"chained_run_{self.run_id}.json"
        payload = {
            "run_id": self.run_id,
            "chaos": self.chaos,
            "project_id": self.project_id,
            "project_key": self.project_key,
            "releases": self.releases,
            "cycles": self.cycles,
            "llm_cost_usd": str(self.llm_cost_usd),
            "stages": [
                {
                    "name": s.name,
                    "started_at": s.started_at.isoformat(),
                    "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                    "metadata": s.metadata,
                }
                for s in self.stages
            ],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path


class ChainedDriver:
    def __init__(self, config: ChainedDriverConfig) -> None:
        self.config = config
        self.report = ChainedRunReport(run_id=uuid.uuid4().hex, chaos=config.chaos)
        self._client = httpx.AsyncClient(
            base_url=config.api_base.rstrip("/"),
            headers={"Authorization": f"Bearer {config.human_token}"},
            timeout=httpx.Timeout(120.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(self, path: str, *, human: bool = True) -> Any:
        headers = {}
        if not human and self.config.viewer_token:
            headers["Authorization"] = f"Bearer {self.config.viewer_token}"
        resp = await self._client.get(path, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def post_json(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        headers: dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        resp = await self._client.post(path, json=body or {}, headers=headers)
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return None

    def dashboard_url_for_release(
        self,
        *,
        project_id: str,
        cycle_id: str,
        approval_id: str,
    ) -> str:
        base = self.config.dashboard_base.rstrip("/")
        return f"{base}/projects/{project_id}/cycles/{cycle_id}?approval={approval_id}"

    def maybe_pause(self, stage_token: str, *, ui: dict[str, Any] | None = None) -> None:
        if (
            stage_token == "approve_release:DC-004"
            and os.environ.get("MVP_CHAOS_SSE_RESTART") == "1"
        ):
            from tests.journey.chained.chaos_hooks import restart_control_api_once

            restart_control_api_once()
        if self.config.pause_before != stage_token:
            return
        pause_path = self.config.pause_file
        pause_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "stage": stage_token,
            "at": datetime.now(UTC).isoformat(),
            "resumed": False,
            "api_base": self.config.api_base.rstrip("/"),
        }
        if ui:
            payload.update(ui)
            approval_id = ui.get("approval_id")
            project_id = ui.get("project_id")
            cycle_id = ui.get("cycle_id")
            if approval_id and project_id and cycle_id and "dashboard_url" not in payload:
                payload["dashboard_url"] = self.dashboard_url_for_release(
                    project_id=str(project_id),
                    cycle_id=str(cycle_id),
                    approval_id=str(approval_id),
                )
        pause_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        deadline = time.time() + 3600
        while time.time() < deadline:
            data = json.loads(pause_path.read_text(encoding="utf-8"))
            if data.get("resumed"):
                return
            time.sleep(2.0)
        raise TimeoutError(f"pause at {stage_token} timed out")

    @staticmethod
    def resume_pause(pause_file: Path = Path("var/olympus/demo/pause.json")) -> None:
        data = json.loads(pause_file.read_text(encoding="utf-8"))
        data["resumed"] = True
        pause_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
