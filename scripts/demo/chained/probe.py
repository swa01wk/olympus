"""HTTP probe for closed-ticket behavior before/after defect injection (Phase 19 §4.3)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProbeResult:
    status_on_closed_update: int
    ok: bool
    detail: str | None = None


def _run_probe_script(repo_root: Path) -> int:
    script = f"""
import sys
from pathlib import Path
root = Path({str(repo_root)!r})
sys.path.insert(0, str(root))
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
created = client.post("/tickets", json={{"title": "probe"}})
if created.status_code not in (200, 201):
    print(created.status_code)
    sys.exit(0)
tid = created.json()["id"]
client.patch(f"/tickets/{{tid}}", json={{"status": "CLOSED"}})
for method in ("patch", "put"):
    fn = getattr(client, method)
    resp = fn(f"/tickets/{{tid}}", json={{"status": "OPEN"}})
    if resp.status_code != 404:
        print(resp.status_code)
        sys.exit(0)
resp = client.post(f"/tickets/{{tid}}/close")
if resp.status_code == 404:
    resp = client.patch(f"/tickets/{{tid}}", json={{"status": "OPEN"}})
print(resp.status_code)
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
        tmp.write(script)
        path = Path(tmp.name)
    try:
        proc = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        out = (proc.stdout or "").strip().splitlines()
        if not out:
            return -1
        try:
            return int(out[-1])
        except ValueError:
            return -1
    finally:
        path.unlink(missing_ok=True)


def probe_closed_ticket_update(repo_root: Path, *, expect: int) -> ProbeResult:
    code = _run_probe_script(repo_root)
    ok = code == expect
    detail = None if ok else f"expected HTTP {expect}, observed {code}"
    return ProbeResult(status_on_closed_update=code, ok=ok, detail=detail)


def assert_pre_injection(repo_root: Path) -> ProbeResult:
    result = probe_closed_ticket_update(repo_root, expect=409)
    if not result.ok:
        raise ValueError(f"AC_ALREADY_VIOLATED: {result.detail}")
    return result


def assert_post_injection(repo_root: Path) -> ProbeResult:
    return probe_closed_ticket_update(repo_root, expect=500)
