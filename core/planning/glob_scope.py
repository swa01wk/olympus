"""Prefix-style glob containment for file_scope / allowed_scope (Phase 06)."""

from __future__ import annotations


def normalize_pattern(pattern: str) -> str:
    p = pattern.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if p.endswith("/**/*.py"):
        p = p[: -len("/**/*.py")] + "/*.py"
    return p


def pattern_allowed(pattern: str) -> bool:
    """Only prefix-style globs: exact path, dir/**, dir/*.py (recursive; dir/**/*.py alias)."""
    p = normalize_pattern(pattern)
    if not p or "**/" in p[2:] or p.count("**") > 1:
        return False
    if "**" in p and not p.endswith("/**"):
        return False
    return "*" not in p.replace("/**", "").replace("*.py", "")


def _prefixes_for_pattern(pattern: str) -> list[str]:
    p = normalize_pattern(pattern)
    if p.endswith("/**"):
        return [p[:-3].rstrip("/") + "/"]
    if p.endswith("/*.py"):
        return [p[:-5].rstrip("/") + "/"]
    if "/" in p or p.endswith(".py") or p.endswith(".md"):
        if p.endswith("/"):
            return [p]
        return [p.rsplit("/", 1)[0] + "/"] if "/" in p else []
    return [p + "/"] if p else []


def path_matches_pattern(path: str, pattern: str) -> bool:
    path_n = normalize_pattern(path)
    pat = normalize_pattern(pattern)
    if pat.endswith("/**"):
        prefix = pat[:-3].rstrip("/") + "/"
        return path_n == prefix.rstrip("/") or path_n.startswith(prefix)
    if pat.endswith("/*.py"):
        prefix = pat[:-5].rstrip("/") + "/"
        return path_n.startswith(prefix) and path_n.endswith(".py")
    return path_n == pat


def scope_contains(container_patterns: list[str], path_patterns: list[str]) -> bool:
    for path_pat in path_patterns:
        if not pattern_allowed(path_pat):
            return False
        if not any(path_matches_pattern(path_pat, c) for c in container_patterns):
            return False
    return True


def intersect_scopes(a: list[str], b: list[str]) -> list[str]:
    out: list[str] = []
    for p in a:
        if any(path_matches_pattern(p, c) for c in b):
            out.append(normalize_pattern(p))
    return sorted(set(out))
