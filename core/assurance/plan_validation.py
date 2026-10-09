"""Deterministic verification plan validation."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.models import VerificationObligation
from core.assurance.pytest_node import pytest_node_id_for_entity
from core.assurance.schemas import VerificationPlan
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion
from core.traceability.models import SpecCodeLink


class PlanValidationService:
    async def validate(
        self,
        session: AsyncSession,
        ic_id: uuid.UUID,
        plan: VerificationPlan,
    ) -> tuple[bool, dict[str, object]]:
        errors: list[str] = []
        ic = await session.get(IntegrationCandidate, ic_id)
        if ic is None or ic.canonical_index_version_id is None:
            return False, {"errors": ["IC_OR_INDEX_MISSING"]}
        version = await session.get(CodeIndexVersion, ic.canonical_index_version_id)
        if version is None:
            return False, {"errors": ["INDEX_VERSION_MISSING"]}
        entities = await session.execute(
            select(CodeEntity).where(CodeEntity.index_version_id == version.id)
        )
        test_node_ids: set[str] = set()
        for e in entities.scalars():
            if e.type != EntityType.TEST:
                continue
            node = pytest_node_id_for_entity(e)
            if node:
                test_node_ids.add(node)
            if e.qualified_name:
                test_node_ids.add(e.qualified_name)
        route_paths = {
            e.qualified_name or e.file_path
            for e in entities.scalars()
            if e.type == EntityType.ROUTE
        }
        obligations = await session.execute(
            select(VerificationObligation).where(
                VerificationObligation.integration_candidate_id == ic_id,
            )
        )
        obl_by_key = {o.subject_key: o for o in obligations.scalars()}
        covered_keys: set[str] = set()
        for check in plan.checks:
            if check.obligation_key not in obl_by_key:
                errors.append(f"UNKNOWN_OBLIGATION:{check.obligation_key}")
                continue
            covered_keys.add(check.obligation_key)
            if check.kind == "EXISTING_TEST":
                if not check.test_node_id or check.test_node_id not in test_node_ids:
                    errors.append(f"TEST_NODE_MISSING:{check.test_node_id}")
            elif check.kind == "API_PROBE":
                probe = check.probe
                if probe is None or probe.path not in route_paths:
                    errors.append(f"ROUTE_MISSING:{probe.path if probe else None}")
            elif check.kind == "AUTHORED_TEST" and (not check.test_code or not check.test_filename):
                errors.append("AUTHORED_TEST_INCOMPLETE")
        for key, obl in obl_by_key.items():
            if not obl.required:
                continue
            if key not in covered_keys and key not in plan.uncovered_obligations:
                link = await session.execute(
                    select(SpecCodeLink).where(
                        SpecCodeLink.spec_id == obl.subject_id,
                        SpecCodeLink.established_index_version_id == version.id,
                    )
                )
                if link.scalar_one_or_none() is None:
                    errors.append(f"REQUIRED_OBLIGATION_UNCOVERED:{key}")
        ok = not errors
        return ok, {"errors": errors, "test_nodes_available": len(test_node_ids)}
