from __future__ import annotations

import json
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from core.execution.sandbox import SandboxConfig, get_sandbox_runner
from core.tools.context import ToolExecutionContext
from core.tools.policy.shell import validate_shell_invocation
from core.tools.shell_policy import load_shell_policy, scrubbed_env


def _parse_junit(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {"junit_present": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"junit_present": True, "junit_bytes": len(text)}


async def run_pytest_in_workspace(
    workspace_path: Path,
    params: dict[str, object],
) -> dict[str, object]:
    runner_name = str(params.get("runner", "pytest"))
    raw_args = params.get("args", [])
    if not isinstance(raw_args, list):
        raw_args = []
    args = [str(x) for x in raw_args]
    category = runner_name if runner_name in {"pytest", "ruff", "mypy"} else "pytest"
    argv = [runner_name, *args[:20]]
    policy = load_shell_policy()
    validate_shell_invocation(category, argv, policy)
    sandbox = get_sandbox_runner()
    sandbox_result = await sandbox.run(
        SandboxConfig(
            workspace_path=workspace_path,
            argv=argv,
            env=scrubbed_env(),
            timeout_s=policy.timeout_s,
            max_output_bytes=policy.max_output_bytes,
            network=False,
        )
    )
    proc_returncode = sandbox_result.returncode
    proc_stdout = sandbox_result.stdout
    proc_stderr = sandbox_result.stderr
    junit_path: Path | None = None
    for arg in args:
        if arg.startswith("--junitxml="):
            junit_path = Path(str(arg.split("=", 1)[1]))
    payload: dict[str, object] = {
        "runner": runner_name,
        "returncode": proc_returncode,
        "stdout": proc_stdout,
        "stderr": proc_stderr,
        "passed": proc_returncode == 0,
        "timed_out": sandbox_result.timed_out,
    }
    if junit_path is not None:
        payload["junit"] = _parse_junit(junit_path)
    return payload


async def test_run(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    assert ctx.workspace_path
    return await run_pytest_in_workspace(ctx.workspace_path, params)


async def test_run_probe(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    assert ctx.workspace_path
    return await run_probe_in_workspace(ctx.workspace_path, params)


async def run_probe_in_workspace(
    workspace_path: Path,
    params: dict[str, object],
) -> dict[str, object]:
    probes_raw = params.get("probes", [])
    if not isinstance(probes_raw, list):
        probes_raw = []
    app_module = str(params.get("app_module", "main:app"))
    port_raw = params.get("port", 8765)
    port = int(port_raw) if isinstance(port_raw, int | str) else 8765
    policy = load_shell_policy()
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as db_file:
        db_path = db_file.name
    env = scrubbed_env()
    env["SUPPORTDESK_DATABASE_URL"] = f"sqlite:///{db_path}"
    proc = subprocess.Popen(
        ["uvicorn", app_module, "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(workspace_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    health_ok = False
    for _ in range(30):
        time.sleep(0.2)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as resp:
                health_ok = resp.status == 200
                break
        except (urllib.error.URLError, TimeoutError):
            continue
    results: list[dict[str, object]] = []
    all_pass = health_ok
    for raw in probes_raw[:10]:
        if not isinstance(raw, dict):
            continue
        method = str(raw.get("method", "GET")).upper()
        path = str(raw.get("path", "/"))
        expected_status = int(raw.get("expected_status", 200))
        url = f"http://127.0.0.1:{port}{path}"
        req = urllib.request.Request(url, method=method)
        if raw.get("body") is not None:
            req.data = json.dumps(raw["body"]).encode()
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=policy.timeout_s) as resp:
                ok = resp.status == expected_status
        except urllib.error.HTTPError as exc:
            ok = exc.code == expected_status
        except urllib.error.URLError:
            ok = False
        results.append({"path": path, "passed": ok})
        all_pass = all_pass and ok
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    Path(db_path).unlink(missing_ok=True)
    return {"passed": all_pass, "probes": results, "health_ok": health_ok}
