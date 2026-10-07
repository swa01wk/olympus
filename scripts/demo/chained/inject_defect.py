"""Deterministic closed-ticket defect injection (Phase 19 §4.3, Q-05 strategy A)."""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class InjectionError(StrEnum):
    AC_ALREADY_VIOLATED = "AC_ALREADY_VIOLATED"
    INJECTION_TARGET_AMBIGUOUS = "INJECTION_TARGET_AMBIGUOUS"
    NO_TARGET = "NO_TARGET"


@dataclass(frozen=True)
class RaiseSite:
    path: Path
    lineno: int
    col_offset: int
    source_line: str


_HTTP409_RE = re.compile(
    r"status_code\s*=\s*(?:409|status\.HTTP_409_CONFLICT)",
    re.MULTILINE,
)


def find_409_raise_sites(tree_path: Path, source: str) -> list[RaiseSite]:
    """Locate raise sites that enforce HTTP 409 in ticket update paths."""
    if "409" not in source and "HTTP_409" not in source:
        return []
    sites: list[RaiseSite] = []
    try:
        tree = ast.parse(source, filename=str(tree_path))
    except SyntaxError:
        return []
    lines = source.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise):
            continue
        segment = ast.get_source_segment(source, node) or ""
        if not _HTTP409_RE.search(segment):
            continue
        line = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ""
        sites.append(
            RaiseSite(
                path=tree_path,
                lineno=node.lineno,
                col_offset=node.col_offset,
                source_line=line.strip(),
            )
        )
    return sites


def transform_409_to_500(source: str, *, site: RaiseSite) -> str:
    """Replace a single 409 raise with unhandled RuntimeError (→ HTTP 500)."""
    lines = source.splitlines(keepends=True)
    idx = site.lineno - 1
    if idx < 0 or idx >= len(lines):
        raise ValueError("invalid raise site line")
    indent = re.match(r"^(\s*)", lines[idx]).group(1)  # type: ignore[union-attr]
    lines[idx] = f'{indent}raise RuntimeError("ticket is closed")\n'
    return "".join(lines)


def inject_defect_in_tree(repo_root: Path, rel_path: str = "app/services/ticket_service.py") -> str:
    """Return new file contents after injection; raises ValueError with InjectionError code."""
    target = repo_root / rel_path
    if not target.is_file():
        raise ValueError(f"{InjectionError.NO_TARGET}: missing {target}")
    original = target.read_text(encoding="utf-8")
    sites = find_409_raise_sites(target, original)
    if len(sites) == 0:
        raise ValueError(f"{InjectionError.NO_TARGET}: no 409 raise in {rel_path}")
    if len(sites) > 1:
        detail = "; ".join(f"{s.path}:{s.lineno}" for s in sites)
        raise ValueError(f"{InjectionError.INJECTION_TARGET_AMBIGUOUS}: {detail}")
    return transform_409_to_500(original, site=sites[0])


def format_external_commit_message() -> str:
    return textwrap.dedent(
        """\
        external: simulate developer bug on closed ticket update

        Authored-by: External Developer <external@supportdesk.invalid>
        """
    ).strip()
