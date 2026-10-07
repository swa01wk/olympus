"""LOCAL repository connector — SYSTEM-only git operations against canonical workspaces."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from core.execution.worktrees.git import GitCli
from core.integrations.connectors.base import (
    ConnectorAction,
    ConnectorHealth,
    ConnectorResult,
    ReconciliationRequest,
)
from core.repositories.credentials import ResolvedCredential
from core.repositories.workspace_locator import WorkspaceLocator


class GitLocalConnector:
    name = "git_local"
    actions = {
        "init_repository",
        "clone_repository",
        "fetch",
        "resolve_branch",
        "resolve_commit",
        "resolve_head",
        "read_metadata",
        "verify_repository",
        "create_branch",
        "merge_candidates",
        "fast_forward_ref",
        "create_tag",
        "baseline_commit",
    }

    def __init__(
        self,
        locator: WorkspaceLocator | None = None,
        git: GitCli | None = None,
    ) -> None:
        self._locator = locator or WorkspaceLocator()
        self._git = git or GitCli()

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        try:
            handler = getattr(self, f"_action_{action.action}")
        except AttributeError:
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="UNKNOWN_ACTION",
                error_detail=action.action,
            )
        result: ConnectorResult = handler(action)
        return result

    async def reconcile(self, request: ReconciliationRequest) -> ConnectorResult:
        return ConnectorResult(status="UNKNOWN", error_class="NOT_IMPLEMENTED")

    async def validate(self) -> ConnectorHealth:
        return ConnectorHealth(ok=True, message="git_local ready")

    def _git_dir(self, logical: str) -> Path:
        return self._locator.resolve("LOCAL_FILESYSTEM", logical)

    def _git_for_credential(self, credential: ResolvedCredential | None) -> GitCli:
        if credential is None:
            return self._git
        secret = credential.secret.get_secret_value()
        return GitCli(credential_env={"OLYMPUS_GIT_CREDENTIAL": secret})

    def _action_init_repository(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        default_branch = str(action.inputs.get("default_branch", "main"))
        dest = self._git_dir(logical)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="ALREADY_EXISTS",
                error_detail=str(logical),
            )
        self._git.run(
            GitCli.hook_disabled_config_args()
            + ["init", "--bare", f"--initial-branch={default_branch}", str(dest)],
            check=True,
        )
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"logical_location": logical, "default_branch": default_branch},
        )

    def _action_baseline_commit(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        default_branch = str(action.inputs.get("default_branch", "main"))
        files: dict[str, str] = dict(action.inputs.get("files", {}))
        author_name = str(action.inputs.get("author_name", "Olympus"))
        author_email = str(action.inputs.get("author_email", "system@olympus.local"))
        message = str(action.inputs.get("message", "chore: initialize repository"))
        git_dir = self._git_dir(logical)
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            self._git.run(
                GitCli.hook_disabled_config_args() + ["init", "-b", default_branch],
                cwd=src,
                check=True,
            )
            for rel, content in files.items():
                target = src / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            self._git.run(["add", "-A"], cwd=src, check=True)
            self._git.run(
                [
                    "-c",
                    f"user.name={author_name}",
                    "-c",
                    f"user.email={author_email}",
                    "commit",
                    "-m",
                    message,
                ],
                cwd=src,
                check=True,
            )
            sha = self._git.run(["rev-parse", "HEAD"], cwd=src, check=True).stdout.strip()
            push_args = GitCli.hook_disabled_config_args() + [
                "push",
                str(git_dir),
                f"HEAD:{default_branch}",
            ]
            self._git.run(push_args, cwd=src, check=True)
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"sha": sha, "branch": default_branch},
        )

    def _action_clone_repository(self, action: ConnectorAction) -> ConnectorResult:
        remote_url = str(action.inputs["remote_url"])
        if not remote_url.startswith("file://"):
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="TRANSPORT_NOT_SUPPORTED",
                error_detail="Only file:// origins in phase 04",
            )
        logical = str(action.inputs["logical_location"])
        dest = self._git_dir(logical)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        credential = action.inputs.get("_credential")
        git = self._git
        if isinstance(credential, ResolvedCredential):
            git = self._git_for_credential(credential)
        git.run(
            GitCli.hook_disabled_config_args()
            + ["clone", "--bare", "--no-recurse-submodules", remote_url, str(dest)],
            check=True,
        )
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"logical_location": logical},
        )

    def _action_fetch(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        remote_url = str(action.inputs.get("remote_url", ""))
        git_dir = self._git_dir(logical)
        if remote_url and not remote_url.startswith("file://"):
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="TRANSPORT_NOT_SUPPORTED",
            )
        args = GitCli.hook_disabled_config_args() + ["fetch", "origin"]
        if remote_url:
            self._git.run(["remote", "add", "origin", remote_url], git_dir=git_dir, check=False)
        self._git.run(args, git_dir=git_dir, check=True)
        heads: dict[str, str] = {}
        result = self._git.run(
            ["for-each-ref", "--format=%(refname:strip=3) %(objectname)", "refs/remotes/origin"],
            git_dir=git_dir,
            check=False,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2:
                heads[parts[0]] = parts[1]
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"remote_heads": heads},
        )

    def _action_resolve_branch(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        requested = action.inputs.get("requested_branch")
        git_dir = self._git_dir(logical)
        if requested:
            branch = str(requested)
        else:
            branch = str(action.inputs.get("default_branch") or "")
            if not branch or branch == "main":
                sym = self._git.run(
                    ["symbolic-ref", "refs/remotes/origin/HEAD"],
                    git_dir=git_dir,
                    check=False,
                )
                if sym.returncode == 0:
                    branch = sym.stdout.strip().split("/")[-1]
                else:
                    head = self._git.run(["symbolic-ref", "HEAD"], git_dir=git_dir, check=False)
                    if head.returncode == 0:
                        branch = head.stdout.strip().split("/")[-1]
                    else:
                        refs = self._git.run(
                            ["for-each-ref", "--format=%(refname:short)", "refs/heads/"],
                            git_dir=git_dir,
                            check=False,
                        )
                        lines = [ln for ln in refs.stdout.splitlines() if ln]
                        branch = lines[0] if lines else "main"
        return ConnectorResult(status="SUCCEEDED", normalized_result={"branch": branch})

    def _action_resolve_head(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        branch = str(action.inputs["branch"])
        git_dir = self._git_dir(logical)
        for ref in (
            f"refs/heads/{branch}",
            f"refs/remotes/origin/{branch}",
            branch,
        ):
            result = self._git.run(["rev-parse", ref], git_dir=git_dir, check=False)
            if result.returncode == 0:
                return ConnectorResult(
                    status="SUCCEEDED",
                    normalized_result={"sha": result.stdout.strip(), "branch": branch},
                )
        return ConnectorResult(
            status="FAILED_FINAL",
            error_class="REF_NOT_FOUND",
            error_detail=branch,
        )

    def _action_resolve_commit(self, action: ConnectorAction) -> ConnectorResult:
        return self._action_resolve_head(action)

    def _action_read_metadata(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        sha = str(action.inputs.get("sha", "HEAD"))
        git_dir = self._git_dir(logical)
        count = self._git.run(["count-objects", "-v"], git_dir=git_dir, check=True)
        size_kb = 0
        count_num = 0
        for line in count.stdout.splitlines():
            if line.startswith("size-pack:"):
                size_kb = int(line.split(":")[1].strip())
            if line.startswith("count:"):
                count_num = int(line.split(":")[1].strip())
        tree = self._git.run(
            ["ls-tree", "--name-only", sha], git_dir=git_dir, check=True
        ).stdout.splitlines()
        modules = self._git.run(["ls-files", "--stage"], git_dir=git_dir, check=False).stdout
        has_submodules = "160000" in modules
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={
                "object_count": count_num,
                "size_kb": size_kb,
                "top_level_tree": tree,
                "has_submodules": has_submodules,
                "has_lfs": False,
            },
        )

    def _action_verify_repository(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        sha = action.inputs.get("sha")
        git_dir = self._git_dir(logical)
        if not git_dir.exists():
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="WORKSPACE_MISSING",
            )
        self._git.run(
            GitCli.hook_disabled_config_args() + ["fsck", "--connectivity-only"],
            git_dir=git_dir,
            check=True,
        )
        if sha:
            self._git.run(
                ["cat-file", "-e", f"{sha}^{{commit}}"],
                git_dir=git_dir,
                check=True,
            )
        return ConnectorResult(status="SUCCEEDED", normalized_result={"verified": True})

    def _action_create_branch(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        branch = str(action.inputs["branch"])
        start_point = str(action.inputs["start_point"])
        git_dir = self._git_dir(logical)
        self._git.run(
            ["branch", branch, start_point],
            git_dir=git_dir,
            check=True,
        )
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"branch": branch, "start_point": start_point},
        )

    def _action_merge_candidates(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        base_sha = str(action.inputs["base_sha"])
        candidate_shas: list[str] = list(action.inputs.get("candidate_shas", []))
        branch = str(action.inputs.get("branch", "olympus/depbase/tmp"))
        git_dir = self._git_dir(logical)
        if not git_dir.exists():
            return ConnectorResult(status="FAILED_FINAL", error_class="WORKSPACE_MISSING")
        self._git.run(["branch", "-f", branch, base_sha], git_dir=git_dir, check=True)
        with tempfile.TemporaryDirectory(prefix="olympus-merge-") as tmp:
            wt_path = Path(tmp) / "wt"
            self._git.run(
                GitCli.hook_disabled_config_args() + ["worktree", "add", str(wt_path), branch],
                git_dir=git_dir,
                check=True,
            )
            head = base_sha
            try:
                for sha in candidate_shas:
                    mb = self._git.run(
                        ["merge-base", "--is-ancestor", sha, "HEAD"],
                        cwd=wt_path,
                        check=False,
                    )
                    if mb.returncode == 0:
                        continue
                    merge = self._git.run(
                        GitCli.hook_disabled_config_args()
                        + [
                            "merge",
                            "--no-ff",
                            "--no-edit",
                            "-m",
                            f"Olympus Integration: merge {sha[:8]}",
                            sha,
                        ],
                        cwd=wt_path,
                        check=False,
                    )
                    if merge.returncode != 0:
                        self._git.run(["merge", "--abort"], cwd=wt_path, check=False)
                        return ConnectorResult(
                            status="FAILED_FINAL",
                            error_class="MERGE_CONFLICT",
                            normalized_result={"conflict": merge.stderr},
                        )
                    head = self._git.run(
                        ["rev-parse", "HEAD"], cwd=wt_path, check=True
                    ).stdout.strip()
            finally:
                self._git.run(
                    GitCli.hook_disabled_config_args()
                    + ["worktree", "remove", "--force", str(wt_path)],
                    git_dir=git_dir,
                    check=False,
                )
            self._git.run(["branch", "-f", branch, head], git_dir=git_dir, check=True)
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"integrated_sha": head, "branch": branch},
        )

    def _action_fast_forward_ref(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        ref = str(action.inputs["ref"])
        target_sha = str(action.inputs["target_sha"])
        git_dir = self._git_dir(logical)
        if not git_dir.exists():
            return ConnectorResult(status="FAILED_FINAL", error_class="WORKSPACE_MISSING")
        current = self._git.run(
            ["rev-parse", ref.replace("refs/heads/", "")],
            git_dir=git_dir,
            check=False,
        )
        if current.returncode != 0:
            return ConnectorResult(status="FAILED_FINAL", error_class="REF_MISSING")
        head = current.stdout.strip()
        if head == target_sha:
            return ConnectorResult(
                status="SUCCEEDED",
                normalized_result={"ref": ref, "sha": target_sha, "idempotent": True},
            )
        ancestor = self._git.run(
            ["merge-base", "--is-ancestor", head, target_sha],
            git_dir=git_dir,
            check=False,
        )
        if ancestor.returncode != 0:
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="NOT_FAST_FORWARD",
                error_detail=f"{head} is not ancestor of {target_sha}",
            )
        branch = ref.removeprefix("refs/heads/")
        self._git.run(["branch", "-f", branch, target_sha], git_dir=git_dir, check=True)
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"ref": ref, "sha": target_sha, "from_sha": head},
        )

    def _action_create_tag(self, action: ConnectorAction) -> ConnectorResult:
        logical = str(action.inputs["logical_location"])
        tag = str(action.inputs["tag"])
        target_sha = str(action.inputs["target_sha"])
        git_dir = self._git_dir(logical)
        if not git_dir.exists():
            return ConnectorResult(status="FAILED_FINAL", error_class="WORKSPACE_MISSING")
        existing = self._git.run(["rev-parse", tag], git_dir=git_dir, check=False)
        if existing.returncode == 0:
            if existing.stdout.strip() == target_sha:
                return ConnectorResult(
                    status="SUCCEEDED",
                    normalized_result={"tag": tag, "sha": target_sha, "idempotent": True},
                )
            return ConnectorResult(status="FAILED_FINAL", error_class="TAG_EXISTS")
        self._git.run(["tag", tag, target_sha], git_dir=git_dir, check=True)
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"tag": tag, "sha": target_sha},
        )


def register_git_local(registry: object) -> None:
    from core.integrations.connectors.registry import ConnectorRegistry

    assert isinstance(registry, ConnectorRegistry)
    registry.register(GitLocalConnector())
