from __future__ import annotations

from pathlib import PurePosixPath


def path_to_module(file_path: str) -> str:
    path = PurePosixPath(file_path)
    parts = path.parent.parts if path.name == "__init__.py" else path.with_suffix("").parts
    return ".".join(p for p in parts if p)


def build_module_index(py_files: dict[str, str]) -> dict[str, str]:
    """Map module qualified name -> file path."""
    index: dict[str, str] = {}
    for path in sorted(py_files):
        index[path_to_module(path)] = path
    return index


def package_paths(py_files: dict[str, str]) -> list[str]:
    packages: set[str] = set()
    for path in py_files:
        parts = PurePosixPath(path).parts
        for i in range(1, len(parts)):
            pkg = "/".join(parts[:i])
            if any(p.startswith(f"{pkg}/") or p == f"{pkg}/__init__.py" for p in py_files):
                packages.add(pkg)
    return sorted(packages)
