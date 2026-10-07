"""Chained driver pause handoff for operator UI walkthrough."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from scripts.demo.chained.driver import ChainedDriver, ChainedDriverConfig


def test_maybe_pause_writes_dashboard_handoff(tmp_path: Path) -> None:
    pause_file = tmp_path / "pause.json"
    driver = ChainedDriver(
        ChainedDriverConfig(
            api_base="http://127.0.0.1:8000",
            human_token="t",
            pause_before="approve_release:DC-004",
            pause_file=pause_file,
            dashboard_base="http://127.0.0.1:3010",
        )
    )

    def resume_after_write() -> None:
        for _ in range(50):
            if pause_file.is_file():
                ChainedDriver.resume_pause(pause_file)
                return
            time.sleep(0.05)
        raise AssertionError("pause file was not written")

    threading.Thread(target=resume_after_write, daemon=True).start()
    driver.maybe_pause(
        "approve_release:DC-004",
        ui={
            "project_id": "11111111-1111-4111-8111-111111111111",
            "cycle_id": "22222222-2222-4222-8222-222222222222",
            "release_id": "33333333-3333-4333-8333-333333333333",
            "approval_id": "44444444-4444-4444-8444-444444444444",
        },
    )

    data = json.loads(pause_file.read_text(encoding="utf-8"))
    assert data["stage"] == "approve_release:DC-004"
    assert data["approval_id"] == "44444444-4444-4444-8444-444444444444"
    assert "dashboard_url" in data
    assert "approval=44444444" in data["dashboard_url"]
    assert data["api_base"] == "http://127.0.0.1:8000"

    ChainedDriver.resume_pause(pause_file)
    assert json.loads(pause_file.read_text(encoding="utf-8"))["resumed"] is True
