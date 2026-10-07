from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.domain.artifacts.models import Artifact
from core.domain.sequences import next_project_key


def content_hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class ArtifactStore:
    def __init__(self) -> None:
        self._root = get_settings().olympus_storage_root

    async def put(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID | None,
        execution_id: uuid.UUID | None,
        kind: str,
        schema_name: str,
        schema_version: str,
        content: bytes | dict[str, Any],
        created_by_actor_id: uuid.UUID | None = None,
    ) -> Artifact:
        if isinstance(content, dict):
            raw = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
            inline: dict[str, Any] | None = content if len(raw) < 4096 else None
        else:
            raw = content
            inline = None
        content_hash = content_hash_bytes(raw)
        storage_ref = self._write_blob(content_hash, raw)
        key = await next_project_key(session, project_id, "artifact", prefix="A")
        row = Artifact(
            key=key,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            execution_id=execution_id,
            kind=kind,
            schema_name=schema_name,
            schema_version=schema_version,
            content_hash=content_hash,
            size_bytes=len(raw),
            storage_ref=storage_ref,
            inline=inline,
            created_by_actor_id=created_by_actor_id,
        )
        session.add(row)
        await session.flush()
        return row

    def _write_blob(self, content_hash: str, raw: bytes) -> str:
        prefix = content_hash[:2]
        rel = f"artifacts/sha256/{prefix}/{content_hash}"
        path = self._root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(raw)
        return rel

    def read_bytes(self, artifact: Artifact) -> bytes:
        path = self._root / artifact.storage_ref
        return path.read_bytes()
