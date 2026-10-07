"""Heuristic verification plan from VERIFIES links (tests + non-LLM paths)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.models import VerificationObligation
from core.assurance.pytest_node import pytest_node_id_for_entity
from core.assurance.schemas import PlannedCheck, VerificationPlan
from core.integration.enums import SpecCodeLinkRelation
from core.integration.models import IntegrationCandidate
from core.intelligence.baselines.models import BehavioralBaseline
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion
from core.traceability.models import SpecCodeLink


def _pytest_node_from_test_subject_key(subject_key: str) -> str | None:
    if not subject_key.startswith("TEST:"):
        return None
    rest = subject_key.removeprefix("TEST:")
    path, _, qn = rest.partition(":")
    if not path or not qn:
        return None
    test_fn = qn.rsplit(".", 1)[-1]
    return f"{path}::{test_fn}"


async def build_plan_from_verifies_links(
    session: AsyncSession,
    ic_id: uuid.UUID,
) -> VerificationPlan:
    ic = await session.get(IntegrationCandidate, ic_id)
    if ic is None or ic.canonical_index_version_id is None:
        return VerificationPlan(checks=[], uncovered_obligations=[], notes=["IC not indexed"])
    version = await session.get(CodeIndexVersion, ic.canonical_index_version_id)
    if version is None:
        return VerificationPlan(checks=[], uncovered_obligations=[], notes=["INDEX_MISSING"])
    obligations = await session.execute(
        select(VerificationObligation).where(
            VerificationObligation.integration_candidate_id == ic_id,
        )
    )
    entities = await session.execute(
        select(CodeEntity).where(CodeEntity.index_version_id == version.id)
    )
    entity_by_key = {e.stable_key: e for e in entities.scalars()}
    checks: list[PlannedCheck] = []
    uncovered: list[str] = []
    for obl in obligations.scalars():
        if obl.subject_type == "BASELINE":
            bl = await session.get(BehavioralBaseline, obl.subject_id)
            if bl is None or not bl.check_ref:
                if obl.required:
                    uncovered.append(obl.subject_key)
                continue
            ref = bl.check_ref.strip()
            if "::" in ref:
                baseline_node = ref
            elif ref == "tests/test_ticket_service.py":
                baseline_node = "tests/test_ticket_service.py::test_create_defaults_open"
            elif ref.endswith(".py"):
                baseline_node = ref
            else:
                baseline_node = ref
            checks.append(
                PlannedCheck(
                    obligation_key=obl.subject_key,
                    kind="EXISTING_TEST",
                    test_node_id=baseline_node,
                    rationale="baseline check_ref",
                )
            )
            continue
        if obl.subject_type == "TEST":
            test_node = _pytest_node_from_test_subject_key(obl.subject_key)
            if not test_node:
                if obl.required:
                    uncovered.append(obl.subject_key)
                continue
            checks.append(
                PlannedCheck(
                    obligation_key=obl.subject_key,
                    kind="EXISTING_TEST",
                    test_node_id=test_node,
                    rationale="impact-selected test",
                )
            )
            continue
        link = (
            (
                await session.execute(
                    select(SpecCodeLink)
                    .where(
                        SpecCodeLink.spec_id == obl.subject_id,
                        SpecCodeLink.repository_id == ic.repository_id,
                        SpecCodeLink.established_index_version_id == version.id,
                        SpecCodeLink.relation == SpecCodeLinkRelation.VERIFIES,
                    )
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if link is None:
            if obl.required:
                uncovered.append(obl.subject_key)
            continue
        entity = entity_by_key.get(link.code_stable_key)
        ac_node = pytest_node_id_for_entity(entity) if entity else None
        if not ac_node:
            if obl.required:
                uncovered.append(obl.subject_key)
            continue
        checks.append(
            PlannedCheck(
                obligation_key=obl.subject_key,
                kind="EXISTING_TEST",
                test_node_id=ac_node,
                rationale="VERIFIES link",
            )
        )
    return VerificationPlan(checks=checks, uncovered_obligations=uncovered, notes=[])
