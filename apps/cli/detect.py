"""Look at a folder and decide: new project (build from a PRD) or existing code (onboard it).

Pure filesystem + git inspection; nothing here talks to Olympus or changes the folder.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Files that describe a project but are not code: a folder with only these is "new".
DOC_SUFFIXES = frozenset({".md", ".markdown", ".txt", ".rst", ".adoc"})
DOC_NAMES = frozenset(
    {
        "license",
        "licence",
        "copying",
        "notice",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        ".ds_store",
    }
)
SKIP_DIRS = frozenset(
    {
        ".git",
        ".olympus",
        ".idea",
        ".vscode",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        ".next",
        "target",
    }
)
PRD_CANDIDATES = ("PRD.md", "prd.md", "docs/PRD.md", "docs/prd.md", "PRD.txt", "prd.txt")

Kind = Literal["new", "existing"]


@dataclass(frozen=True)
class Detection:
    folder: Path
    kind: Kind
    is_git: bool
    has_commits: bool
    dirty: bool
    code_files: list[str] = field(default_factory=list)
    prd: Path | None = None

    @property
    def code_count(self) -> int:
        return len(self.code_files)


def _git(folder: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=folder, capture_output=True, text=True, check=False, timeout=60
    )


def is_git_repo(folder: Path) -> bool:
    result = _git(folder, "rev-parse", "--show-toplevel")
    return result.returncode == 0 and Path(result.stdout.strip()).resolve() == folder.resolve()


def has_commits(folder: Path) -> bool:
    return _git(folder, "rev-parse", "--verify", "--quiet", "HEAD").returncode == 0


def is_dirty(folder: Path) -> bool:
    result = _git(folder, "status", "--porcelain")
    return result.returncode == 0 and bool(result.stdout.strip())


def is_doc(rel_path: str) -> bool:
    name = Path(rel_path).name.lower()
    if name in DOC_NAMES:
        return True
    stem = Path(name).stem
    return Path(name).suffix in DOC_SUFFIXES or stem in {"readme", "changelog", "prd"}


def _listed_files(folder: Path, git: bool) -> list[str]:
    if git:
        result = _git(folder, "ls-files", "--cached", "--others", "--exclude-standard")
        if result.returncode == 0:
            return [line for line in result.stdout.splitlines() if line.strip()]
    files: list[str] = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            files.append(str(Path(root, name).relative_to(folder)))
    return files


def find_prd(folder: Path, explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        return (path if path.is_absolute() else folder / path).resolve()
    for candidate in PRD_CANDIDATES:
        path = folder / candidate
        if path.is_file():
            return path
    return None


def detect(folder: Path, prd: str | None = None) -> Detection:
    folder = folder.resolve()
    git = is_git_repo(folder)
    files = _listed_files(folder, git)
    code = sorted(f for f in files if not is_doc(f) and not _in_skipped_dir(f))
    return Detection(
        folder=folder,
        kind="existing" if code else "new",
        is_git=git,
        has_commits=git and has_commits(folder),
        dirty=git and is_dirty(folder),
        code_files=code,
        prd=find_prd(folder, prd),
    )


def _in_skipped_dir(rel_path: str) -> bool:
    return any(part in SKIP_DIRS for part in Path(rel_path).parts[:-1])


SECRET_NAMES = frozenset({".env", "id_rsa", "id_ed25519", ".npmrc", ".pypirc", "credentials.json"})
SECRET_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx"})


def looks_secret(folder: Path) -> list[str]:
    """Files `git add -A` would pick up that look like credentials (not ignored by git)."""
    git = is_git_repo(folder)
    found = []
    for rel in _listed_files(folder, git):
        name = Path(rel).name.lower()
        if _in_skipped_dir(rel):
            continue
        if (
            name in SECRET_NAMES
            or (name.startswith(".env") and name not in {".env.example", ".env.sample"})
            or Path(name).suffix in SECRET_SUFFIXES
        ):
            found.append(rel)
    return sorted(found)
