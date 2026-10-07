from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath

from core.execution.worktrees.git import GitCli, GitCliError
from core.repositories.git_inspect import GitInspector


@dataclass(frozen=True)
class TreeEntry:
    path: str
    mode: str
    object_type: str
    sha: str


@dataclass(frozen=True)
class FileGitMetadata:
    last_commit_sha: str
    author_date: str
    commit_count: int


class GitSourceReader:
    """Read repository tree and blob contents at an exact commit SHA (bare git-dir)."""

    def __init__(
        self,
        git_dir: str,
        *,
        git: GitCli | None = None,
        inspector: GitInspector | None = None,
    ) -> None:
        from pathlib import Path

        self._git_dir = Path(git_dir)
        self._git = git or GitCli()
        self._inspector = inspector or GitInspector(self._git)

    def ensure_commit(self, sha: str) -> None:
        if not self._inspector.commit_exists(self._git_dir, sha):
            from core.domain.exceptions import DomainError

            raise DomainError(
                code="COMMIT_NOT_FOUND",
                message=f"Commit {sha} not found in repository object store",
                details={"commit_sha": sha},
            )

    def list_tree(self, sha: str) -> list[TreeEntry]:
        self.ensure_commit(sha)
        result = self._git.run(
            ["ls-tree", "-r", sha],
            git_dir=self._git_dir,
        )
        entries: list[TreeEntry] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            meta, path = line.split("\t", 1)
            if ".." in PurePosixPath(path).parts:
                continue
            mode, obj_type, obj_sha = meta.split()
            if obj_type != "blob":
                continue
            entries.append(TreeEntry(path=path, mode=mode, object_type=obj_type, sha=obj_sha))
        entries.sort(key=lambda e: e.path)
        return entries

    def read_blob(self, sha: str) -> bytes:
        result = self._git.run(
            ["cat-file", "-p", sha],
            git_dir=self._git_dir,
        )
        return result.stdout.encode("utf-8")

    def read_file_at_commit(self, commit_sha: str, path: str) -> bytes | None:
        for entry in self.list_tree(commit_sha):
            if entry.path == path:
                return self.read_blob(entry.sha)
        return None

    def file_metadata_at_commit(self, commit_sha: str, path: str) -> FileGitMetadata | None:
        self.ensure_commit(commit_sha)
        log = self._git.run(
            ["log", "-1", commit_sha, "--format=%H%x00%aI", "--", path],
            git_dir=self._git_dir,
            check=False,
        )
        if log.returncode != 0 or not log.stdout.strip():
            return None
        parts = log.stdout.strip().split("\x00", 1)
        last_sha = parts[0]
        author_date = parts[1] if len(parts) > 1 else ""
        count_result = self._git.run(
            ["rev-list", "--count", commit_sha, "--", path],
            git_dir=self._git_dir,
            check=False,
        )
        count = 0
        if count_result.returncode == 0 and count_result.stdout.strip().isdigit():
            count = int(count_result.stdout.strip())
        return FileGitMetadata(
            last_commit_sha=last_sha,
            author_date=author_date,
            commit_count=count,
        )

    def read_text_files_at_commit(
        self, commit_sha: str, *, suffixes: tuple[str, ...] = (".py",)
    ) -> dict[str, str]:
        files: dict[str, str] = {}
        for entry in self.list_tree(commit_sha):
            if not any(entry.path.endswith(s) for s in suffixes):
                continue
            if ".." in PurePosixPath(entry.path).parts:
                continue
            try:
                raw = self.read_blob(entry.sha)
            except GitCliError:
                continue
            files[entry.path] = raw.decode("utf-8", errors="replace")
        return files

    def file_churn_stats(self, commit_sha: str, *, limit: int = 10) -> list[dict[str, object]]:
        self.ensure_commit(commit_sha)
        result = self._git.run(
            ["log", "--pretty=format:", "--name-only", commit_sha],
            git_dir=self._git_dir,
            check=False,
        )
        counts: Counter[str] = Counter()
        for line in result.stdout.splitlines():
            path = line.strip()
            if path and ".." not in PurePosixPath(path).parts:
                counts[path] += 1
        top = counts.most_common(limit)
        out: list[dict[str, object]] = []
        for path, n in top:
            meta = self.file_metadata_at_commit(commit_sha, path)
            out.append(
                {
                    "path": path,
                    "commit_count": n,
                    "last_commit_sha": meta.last_commit_sha if meta else None,
                }
            )
        return out

    def diff_name_status(self, parent_sha: str, new_sha: str) -> tuple[list[str], list[str]]:
        """Return (changed_or_added_paths, deleted_paths) for Python sources."""
        self.ensure_commit(parent_sha)
        self.ensure_commit(new_sha)
        result = self._git.run(
            ["diff", "--name-status", parent_sha, new_sha],
            git_dir=self._git_dir,
        )
        changed: list[str] = []
        deleted: list[str] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            status, path = parts[0].strip(), parts[1].strip()
            if not path.endswith(".py"):
                continue
            if status.startswith("D"):
                deleted.append(path)
            else:
                changed.append(path)
        return changed, deleted

    def read_dependency_manifests(self, commit_sha: str) -> dict[str, str]:
        manifests: dict[str, str] = {}
        for entry in self.list_tree(commit_sha):
            name = PurePosixPath(entry.path).name
            if name == "pyproject.toml" or re.match(r"requirements.*\.txt$", name):
                try:
                    manifests[entry.path] = self.read_blob(entry.sha).decode(
                        "utf-8", errors="replace"
                    )
                except GitCliError:
                    continue
        return manifests
