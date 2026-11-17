from __future__ import annotations

import re
import subprocess

from core.tools.context import ToolExecutionContext
from core.tools.paths import assert_write_scope, resolve_in_workspace


async def repo_read(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    path = str(params["path"])
    assert ctx.workspace_path
    target = resolve_in_workspace(ctx.workspace_path, path)
    content = target.read_text(encoding="utf-8", errors="replace")
    return {"path": path, "content": content}


async def repo_list(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    assert ctx.workspace_path
    prefix = str(params.get("prefix", ""))
    root = resolve_in_workspace(ctx.workspace_path, prefix or ".")
    files: list[str] = []
    for p in root.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            files.append(str(p.relative_to(ctx.workspace_path.resolve())))
    return {"files": sorted(files)}


async def repo_search(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    assert ctx.workspace_path
    pattern = str(params["pattern"])
    try:
        proc = subprocess.run(
            ["rg", "--json", pattern, str(ctx.workspace_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode in (0, 1):
            return {"matches": proc.stdout.splitlines()[:200], "engine": "ripgrep"}
    except FileNotFoundError:
        pass
    matches: list[str] = []
    for path in ctx.workspace_path.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if pattern in text:
                matches.append(str(path.relative_to(ctx.workspace_path.resolve())))
    return {"matches": matches[:200], "engine": "python"}


_ESCAPES = re.compile(r"\\(n|t|r|\"|\\)")
_ESCAPE_VALUES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def _undo_double_escaping(content: str) -> str:
    """Models sometimes JSON-escape file content twice, so a whole multi-line file arrives as
    one line with literal ``\\n`` sequences and no real newline. Decode that case only: any
    real newline means the content is already plain text."""
    if "\n" in content or content.count("\\n") < 2:
        return content
    return _ESCAPES.sub(lambda m: _ESCAPE_VALUES[m.group(1)], content)


async def repo_write(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    assert ctx.workspace_path and ctx.contract
    path = str(params["path"])
    content = _undo_double_escaping(str(params.get("content", "")))
    target = resolve_in_workspace(ctx.workspace_path, path)
    assert_write_scope(target, ctx.workspace_path, ctx.contract.allowed_scope)
    if target.is_file() and target.read_text(encoding="utf-8", errors="replace") == content:
        # Say so explicitly: a model that cannot tell its edit was a no-op keeps re-sending it.
        return {
            "path": path,
            "bytes": len(content.encode()),
            "unchanged": True,
            "note": "This file already has exactly this content, so nothing changed. Make the "
            "actual fix (different content), or run the tests and commit if you are done.",
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": path, "bytes": len(content.encode())}


async def repo_delete(ctx: ToolExecutionContext, params: dict[str, object]) -> dict[str, object]:
    assert ctx.workspace_path and ctx.contract
    path = str(params["path"])
    target = resolve_in_workspace(ctx.workspace_path, path)
    assert_write_scope(target, ctx.workspace_path, ctx.contract.allowed_scope)
    if target.is_file():
        target.unlink()
    return {"path": path, "deleted": True}
