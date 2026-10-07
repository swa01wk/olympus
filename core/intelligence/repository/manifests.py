from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedManifest:
    name: str
    raw_path: str
    dependencies: list[tuple[str, str | None]]


_PYPROJECT_NAME = re.compile(r'name\s*=\s*"([^"]+)"', re.MULTILINE)
_REQ_LINE = re.compile(r"^([a-zA-Z0-9_.-]+)(?:==([^;\s]+))?", re.MULTILINE)


def parse_pyproject(text: str, path: str) -> ParsedManifest:
    name_match = _PYPROJECT_NAME.search(text)
    name = name_match.group(1) if name_match else path
    deps: list[tuple[str, str | None]] = []
    inline = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if inline:
        for m in re.finditer(r'"([^"]+)"', inline.group(1)):
            pkg = m.group(1).split("[", 1)[0]
            if ">=" in pkg:
                n = pkg.split(">=", 1)[0]
                deps.append((n.strip(), None))
            elif "==" in pkg:
                n, v = pkg.split("==", 1)
                deps.append((n.strip(), v.strip()))
            else:
                deps.append((pkg.strip(), None))
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies") and "=" in stripped and inline is None:
            in_deps = True
            continue
        if in_deps:
            if stripped.startswith("]"):
                in_deps = False
                continue
            line_match = re.match(r'"([^"]+)"', stripped.strip(","))
            if line_match:
                pkg = line_match.group(1).split("[", 1)[0]
                if "==" in pkg:
                    n, v = pkg.split("==", 1)
                    deps.append((n.strip(), v.strip()))
                else:
                    deps.append((pkg.strip(), None))
    return ParsedManifest(name=name, raw_path=path, dependencies=deps)


def parse_requirements(text: str, path: str) -> ParsedManifest:
    deps: list[tuple[str, str | None]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = _REQ_LINE.match(line)
        if m:
            deps.append((m.group(1), m.group(2)))
    return ParsedManifest(name=path, raw_path=path, dependencies=deps)
