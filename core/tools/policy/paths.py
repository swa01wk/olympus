"""Path confinement with traversal and symlink hardening."""

from __future__ import annotations

import fnmatch
import os
import unicodedata
from pathlib import Path

from core.tools.paths import PathPolicyViolation, assert_write_scope, deny_cross_workspace

__all__ = ["PathPolicyViolation", "assert_write_scope", "deny_cross_workspace"]


def normalize_relative_path(relative_path: str) -> str:
    raw = relative_path.strip().replace("\\", "/")
    if raw.startswith("./"):
        raw = raw[2:]
    # Unicode normalization — block homoglyph tricks
    raw = unicodedata.normalize("NFC", raw)
    if raw.startswith("/") or raw.startswith("~"):
        raise PathPolicyViolation("absolute paths denied")
    # Collapse // and detect encoded traversal
    parts: list[str] = []
    for part in Path(raw).parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise PathPolicyViolation("path traversal denied")
        if part.lower() == ".git" or part == ".olympus":
            raise PathPolicyViolation("restricted path segment")
        parts.append(part)
    return "/".join(parts)


def resolve_in_workspace(workspace_root: Path, relative_path: str) -> Path:
    normalized = normalize_relative_path(relative_path)
    candidate = (workspace_root / normalized).resolve()
    root = workspace_root.resolve()
    if root not in candidate.parents and candidate != root:
        raise PathPolicyViolation("path escapes workspace")
    if candidate.exists() and not os.path.samefile(candidate, candidate.resolve()):
        raise PathPolicyViolation("symlink escape")
    rel = candidate.relative_to(root)
    if rel.parts and rel.parts[0] == ".git":
        raise PathPolicyViolation(".git access denied")
    if ".olympus" in rel.parts:
        raise PathPolicyViolation(".olympus access denied")
    return candidate


def match_allowed_scope(rel: str, allowed_scope: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, pattern) for pattern in allowed_scope)
