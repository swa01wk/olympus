"""Loads hashed policy YAML into immutable policy_versions rows."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.canonical_json import sha256_hex
from core.domain.enums import ApprovalType
from core.domain.policy.models import PolicyVersion


class PolicyService:
    def __init__(self, content: dict[str, Any], version_row: PolicyVersion | None = None) -> None:
        self._content = content
        self._version_row = version_row

    @property
    def version_row(self) -> PolicyVersion | None:
        return self._version_row

    def current(self) -> PolicyVersion | None:
        return self._version_row

    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self._content
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def approval_required(
        self, approval_type: ApprovalType, _context: dict[str, Any] | None = None
    ) -> bool:
        required = self.get("approvals_required", {})
        if not isinstance(required, dict):
            return False
        return bool(required.get(approval_type.value, False))


def load_policy_file() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "config" / "policy" / "default.yaml"
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError("Policy file must be a mapping")
    return data


async def ensure_policy_version(session: AsyncSession) -> PolicyService:
    content = load_policy_file()
    content_hash = sha256_hex(content)
    result = await session.execute(
        select(PolicyVersion).where(PolicyVersion.content_hash == content_hash)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = PolicyVersion(
            name="default",
            version=int(content.get("version", 1)),
            content=content,
            content_hash=content_hash,
        )
        session.add(row)
        await session.flush()
    return PolicyService(content, row)


@lru_cache
def get_cached_policy_content() -> dict[str, Any]:
    return load_policy_file()
