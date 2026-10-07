from __future__ import annotations

from collections.abc import Iterable


def detect_frameworks(
    dependencies: Iterable[tuple[str, str | None]],
    imports: Iterable[str],
    source_text: str,
) -> list[str]:
    dep_names = {d[0].lower().replace("_", "-") for d in dependencies}
    found: set[str] = set()
    mapping = {
        "fastapi": "fastapi",
        "sqlalchemy": "sqlalchemy",
        "pydantic": "pydantic",
        "pytest": "pytest",
    }
    for key, label in mapping.items():
        if key in dep_names:
            found.add(label)
    import_blob = " ".join(imports).lower()
    for key, label in mapping.items():
        if key.replace("-", "") in import_blob.replace("_", ""):
            found.add(label)
    lower = source_text.lower()
    if "fastapi()" in lower or "from fastapi" in lower:
        found.add("fastapi")
    if "sqlalchemy" in lower or "declarativebase" in lower:
        found.add("sqlalchemy")
    if "pytest" in lower or "testclient" in lower:
        found.add("pytest")
    return sorted(found)
