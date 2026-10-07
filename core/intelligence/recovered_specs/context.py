from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import KnowledgeClass
from core.intelligence.brownfield.models import ObservedBehavior, RepositoryDiscovery
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion
from core.product_model.models import KnowledgeItem
from core.traceability.models import RepositoryIndexPointer

_FORBIDDEN_PREFIXES = (
    "FEATURE_SPEC",
    "FEATURE",
    "CAPABILITY",
    "ARCHITECTURE",
    "IMPLEMENTATION_SPEC",
)


class ScoutContextBuilder:
    async def build(
        self,
        session: AsyncSession,
        delivery_cycle_id: uuid.UUID,
        *,
        other_cycle_id: uuid.UUID | None = None,
    ) -> tuple[dict[str, Any], str]:
        cycle = await session.get(DeliveryCycle, delivery_cycle_id)
        if cycle is None or cycle.repository_id is None or cycle.base_sha is None:
            raise ValueError("cycle not ready")
        discovery = (
            await session.execute(
                select(RepositoryDiscovery).where(
                    RepositoryDiscovery.delivery_cycle_id == delivery_cycle_id,
                    RepositoryDiscovery.commit_sha == cycle.base_sha,
                )
            )
        ).scalar_one_or_none()
        pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
        index_version_id = pointer.canonical_index_version_id if pointer else None
        entities: list[dict[str, str]] = []
        if index_version_id:
            version = await session.get(CodeIndexVersion, index_version_id)
            if version and version.commit_sha == cycle.base_sha:
                rows = (
                    await session.execute(
                        select(CodeEntity).where(CodeEntity.index_version_id == version.id)
                    )
                ).scalars()
                entities = [{"stable_key": e.stable_key, "type": e.type.value} for e in rows]
        behaviors = (
            (
                await session.execute(
                    select(ObservedBehavior).where(
                        ObservedBehavior.delivery_cycle_id == delivery_cycle_id
                    )
                )
            )
            .scalars()
            .all()
        )
        facts = (
            (
                await session.execute(
                    select(KnowledgeItem).where(
                        KnowledgeItem.delivery_cycle_id == delivery_cycle_id,
                        KnowledgeItem.knowledge_class == KnowledgeClass.FACT,
                    )
                )
            )
            .scalars()
            .all()
        )
        manifest_refs: list[str] = []
        if discovery:
            manifest_refs.append(f"discovery:{discovery.id}")
        if index_version_id:
            manifest_refs.append(f"index:{index_version_id}")
        for b in behaviors:
            manifest_refs.append(f"behavior:{b.key}")
        for f in facts:
            manifest_refs.append(f"fact:{f.id}")
        for ent in entities[:200]:
            manifest_refs.append(f"code:{ent['stable_key']}")
        manifest_refs = sorted(set(manifest_refs))
        for ref in manifest_refs:
            for forbidden in _FORBIDDEN_PREFIXES:
                if ref.startswith(forbidden):
                    raise ValueError(f"forbidden ref in manifest: {ref}")
        if other_cycle_id and other_cycle_id != delivery_cycle_id:
            foreign = (
                await session.execute(
                    select(KnowledgeItem.id).where(
                        KnowledgeItem.delivery_cycle_id == other_cycle_id
                    )
                )
            ).first()
            if foreign:
                raise ValueError("cross-cycle artifact leak")
        payload = {
            "delivery_cycle_id": str(delivery_cycle_id),
            "base_sha": cycle.base_sha,
            "discovery": discovery.content if discovery else {},
            "index_entities": entities,
            "observed_behaviors": [
                {"key": b.key, "kind": b.kind.value, "description": b.description}
                for b in behaviors
            ],
            "facts": [{"id": str(f.id), "statement": f.statement} for f in facts],
            "manifest_refs": manifest_refs,
        }
        return payload, sha256_hex({"refs": manifest_refs})
