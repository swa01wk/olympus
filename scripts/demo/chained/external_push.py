"""Push defect commit to Gitea and sync repository (Phase 19 §4.3 / Phase 16)."""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
from scripts.demo.chained.inject_defect import format_external_commit_message, inject_defect_in_tree
from scripts.demo.chained.probe import assert_post_injection, assert_pre_injection


@dataclass(frozen=True)
class ExternalPushResult:
    before_sha: str
    after_sha: str
    classification: str | None


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout.strip()


def apply_defect_and_push_to_gitea(
    repo_root: Path,
    *,
    gitea_url: str,
    owner: str,
    repo_name: str,
    token: str,
) -> ExternalPushResult:
    assert_pre_injection(repo_root)
    new_source = inject_defect_in_tree(repo_root)
    target = repo_root / "app/services/ticket_service.py"
    target.write_text(new_source, encoding="utf-8")
    assert_post_injection(repo_root)

    before_sha = _git(repo_root, "rev-parse", "HEAD")
    _git(repo_root, "config", "user.email", "external@supportdesk.invalid")
    _git(repo_root, "config", "user.name", "External Developer")
    _git(repo_root, "add", "app/services/ticket_service.py")
    _git(repo_root, "commit", "-m", format_external_commit_message())
    after_sha = _git(repo_root, "rev-parse", "HEAD")

    base = gitea_url.rstrip("/")
    if base.startswith("https://"):
        host = base[len("https://") :]
        remote = f"https://{owner}:{token}@{host}/{owner}/{repo_name}.git"
    elif base.startswith("http://"):
        host = base[len("http://") :]
        remote = f"http://{owner}:{token}@{host}/{owner}/{repo_name}.git"
    else:
        remote = f"http://{owner}:{token}@{base}/{owner}/{repo_name}.git"
    _git(repo_root, "remote", "remove", "mvp-external")
    _git(repo_root, "remote", "add", "mvp-external", remote)
    _git(repo_root, "push", "mvp-external", "HEAD:refs/heads/main")
    return ExternalPushResult(before_sha=before_sha, after_sha=after_sha, classification=None)


async def sync_repository_via_api(
    api_base: str,
    token: str,
    repository_id: uuid.UUID,
) -> dict[str, object]:
    async with httpx.AsyncClient(
        base_url=api_base.rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=120.0,
    ) as client:
        resp = await client.post(f"/repositories/{repository_id}/sync")
        resp.raise_for_status()
        return resp.json()
