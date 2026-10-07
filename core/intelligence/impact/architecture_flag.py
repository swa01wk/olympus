"""Heuristic: suggest architecture delta when impact escapes approved scope."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.enums import SpecStatus
from core.intelligence.code_index.models import CodeEntity
from core.intelligence.impact.traversal import TraversalHit
from core.planning.architecture.service import ArchitectureService
from core.planning.glob_scope import path_matches_pattern
from core.planning.models import ImplementationSpec
from core.product_model.models import FeatureSpec


class ArchitectureDeltaHeuristic:
    async def suggest(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        feature_spec_id: uuid.UUID,
        hits: dict[str, TraversalHit],
        delta_changes: dict[str, object],
    ) -> bool:
        arch = await ArchitectureService().get_approved(session, project_id)
        if arch is None:
            return True
        arch_body = ArchitectureService().parse_body(arch)
        component_dirs = {c.directory.rstrip("/") for c in arch_body.components}
        dir_patterns = [e.path for e in arch_body.directory_conventions] + list(component_dirs)

        impl_dirs: set[str] = set()
        spec = await session.get(FeatureSpec, feature_spec_id)
        if spec is not None:
            impls = await session.execute(
                select(ImplementationSpec).where(
                    ImplementationSpec.feature_spec_id == spec.id,
                    ImplementationSpec.status == SpecStatus.APPROVED,
                )
            )
            for impl in impls.scalars():
                body = impl.body or {}
                for glob in body.get("file_scope") or []:
                    impl_dirs.add(str(glob).split("*")[0].rstrip("/"))

        for hit in hits.values():
            ent: CodeEntity = hit.entity
            fp = ent.file_path or ""
            in_arch = any(path_matches_pattern(fp, pat) for pat in dir_patterns)
            in_impl = any(fp.startswith(d) for d in impl_dirs if d)
            if fp and not in_arch and not in_impl:
                return True

        rules_block = delta_changes.get("rules")
        rules_added: list[object] = []
        if isinstance(rules_block, dict):
            added = rules_block.get("added")
            if isinstance(added, list):
                rules_added = added
        return any("integrat" in str(r).lower() for r in rules_added)
