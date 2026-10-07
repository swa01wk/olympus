from __future__ import annotations

import hashlib

from core.config.settings import get_settings
from core.execution.artifacts import content_hash_bytes


class ContentAddressedStore:
    def __init__(self) -> None:
        self._root = get_settings().olympus_storage_root

    def put_bytes(self, raw: bytes, *, prefix: str = "inbound") -> tuple[str, str]:
        content_hash = content_hash_bytes(raw)
        rel = f"{prefix}/sha256/{content_hash[:2]}/{content_hash}"
        path = self._root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(raw)
        return rel, content_hash

    def read(self, storage_ref: str) -> bytes:
        return (self._root / storage_ref).read_bytes()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
