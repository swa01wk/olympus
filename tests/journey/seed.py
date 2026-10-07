"""Trusted-project seed for Feature Change journey (human-authored YAML inputs)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    DeliveryCycleType,
    EntityStatus,
    EvidenceRequirement,
    ModelOrigin,
    ProjectReadiness,
    SpecKind,
    SpecStatus,
)
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository
from core.domain.sequences import next_project_key
from core.integration.enums import SpecCodeLinkOrigin, SpecCodeLinkRelation, SpecCodeLinkStatus
from core.intelligence.baselines.enums import (
    BaselineActivation,
    BaselineCheckKind,
    BaselineSource,
    BaselineStatus,
)
from core.intelligence.baselines.models import BaselineSet, BaselineSetItem, BehavioralBaseline
from core.intelligence.code_index.canonical_service import CanonicalIndexService
from core.planning.architecture.service import ArchitectureService
from core.planning.implementation_specs.service import ImplementationSpecService
from core.product_model.models import AcceptanceCriterion, Feature, FeatureSpec
from core.product_model.schemas import FeatureSpecBody
from core.traceability.models import RepositoryIndexPointer, SpecCodeLink
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.code_index_harness import SUPPORTDESK_R1
from tests.fixtures.planning_harness import (
    create_ticket_implementation_spec,
    supportdesk_architecture_proposal,
)
from tests.fixtures.repositories import materialize_fixture_repository

TRUSTED_SEED = (
    Path(__file__).resolve().parents[1] / "fixtures" / "supportdesk" / "trusted_seed.yaml"
)
DEFAULT_SEED = TRUSTED_SEED


@dataclass
class TrustedProjectSeed:
    project_id: uuid.UUID
    repository_id: uuid.UUID
    commit_sha: str
    index_version_id: uuid.UUID
    feature_id: uuid.UUID
    feature_spec_id: uuid.UUID
    implementation_spec_id: uuid.UUID
    baseline_set_id: uuid.UUID
    ac_by_key: dict[str, uuid.UUID]


def _load_seed(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError("trusted_seed.yaml must be a mapping")
    return data


async def seed_trusted_project(
    session: AsyncSession,
    repo_fixture: Path,
    seed_yaml: Path,
    ctx: CommandContext,
) -> TrustedProjectSeed:
    """Materialize R1 repo, index, approved spec/arch/impl, baselines, READY_FOR_CHANGE."""
    cfg = _load_seed(seed_yaml)
    suffix = uuid.uuid4().hex[:8]
    project_key = f"{cfg.get('project_key', 'SUPPORTDESK-TRUSTED')}-{suffix}"
    project = Project(
        key=project_key,
        name=str(cfg.get("project_name", "SupportDesk Trusted")),
    )
    session.add(project)
    await session.flush()

    repo, sha = await materialize_fixture_repository(session, project, repo_fixture, ctx)
    repo_row = await session.get(Repository, repo.id)
    assert repo_row is not None

    r1_key = await next_project_key(session, project.id, "delivery_cycle", prefix="DC")
    r1_cycle = DeliveryCycle(
        project_id=project.id,
        key=r1_key,
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="Trusted seed R1",
        state="COMPLETE",
        state_version=0,
        opened_by_actor_id=ctx.actor.id,
        repository_id=repo.id,
        base_sha=sha,
    )
    session.add(r1_cycle)
    await session.flush()

    if repo_row.canonical_commit != sha:
        raise RuntimeError("fixture materialization must set canonical_commit to HEAD")

    version = await CanonicalIndexService().promote_repository_snapshot(session, repo.id, sha, ctx)
    pointer = await session.get(RepositoryIndexPointer, repo.id)
    if pointer is None:
        pointer = RepositoryIndexPointer(repository_id=repo.id)
        session.add(pointer)
    pointer.canonical_index_version_id = version.id
    await session.flush()

    from core.repositories.revision import RepositoryRevisionService

    await RepositoryRevisionService().mark_released(session, repo.id, sha, uuid.uuid4(), ctx)

    feature = Feature(
        project_id=project.id,
        key=str(cfg["feature_key"]),
        name=str(cfg.get("feature_name", cfg["feature_key"])),
        description="Trusted seed feature",
        status=EntityStatus.PROPOSED,
        origin=ModelOrigin.HUMAN,
        source_refs=[],
    )
    session.add(feature)
    await session.flush()

    fs_cfg = cfg.get("feature_spec") or {}
    body = FeatureSpecBody(
        behavior=str(fs_cfg.get("behavior", "Tickets")),
        summary=str(fs_cfg.get("summary", "Tickets")),
        inputs=list(fs_cfg.get("inputs") or []),
        outputs=list(fs_cfg.get("outputs") or []),
        rules=list(fs_cfg.get("rules") or []),
        constraints=list(fs_cfg.get("constraints") or []),
    )
    body_dict = body.model_dump(mode="json")
    spec = FeatureSpec(
        project_id=project.id,
        feature_id=feature.id,
        lineage_key=str(cfg["spec_lineage"]),
        version=1,
        status=SpecStatus.APPROVED,
        spec_kind=SpecKind.CANONICAL,
        body=body_dict,
        content_hash=sha256_hex(body_dict),
    )
    session.add(spec)
    await session.flush()

    ac_by_key: dict[str, uuid.UUID] = {}
    for ac_row in cfg.get("acceptance_criteria") or []:
        ac = AcceptanceCriterion(
            feature_spec_id=spec.id,
            lineage_key=str(ac_row["lineage_key"]),
            statement=str(ac_row.get("statement", "")),
            given=ac_row.get("given"),
            when=ac_row.get("when"),
            then=ac_row.get("then"),
            mandatory=bool(ac_row.get("mandatory", True)),
            evidence_requirement=EvidenceRequirement(
                str(ac_row.get("evidence_requirement", "EXECUTABLE"))
            ),
            requirement_keys=[],
        )
        session.add(ac)
        await session.flush()
        ac_by_key[ac.lineage_key] = ac.id

    arch = await ArchitectureService().persist_proposal(
        session,
        project_id=project.id,
        proposal=supportdesk_architecture_proposal(),
        execution_id=None,
        ctx=ctx,
    )
    arch.status = SpecStatus.APPROVED
    await session.flush()

    impl_draft = create_ticket_implementation_spec()
    impl = await ImplementationSpecService().persist_draft(
        session,
        feature_spec_id=spec.id,
        draft=impl_draft,
        execution_id=None,
        ctx=ctx,
    )
    impl.lineage_key = str(cfg.get("implementation_spec_lineage", impl.lineage_key))
    impl.status = SpecStatus.APPROVED
    impl.architecture_id = arch.id
    impl.kind = "FULL"
    await session.flush()

    for link in cfg.get("spec_code_links") or []:
        ac_id = ac_by_key.get(str(link.get("ac_lineage_key", "")))
        spec_lineage = str(link.get("spec_lineage_key") or spec.lineage_key)
        if ac_id:
            spec_type = "AC"
            spec_ref_id = ac_id
            spec_lineage_key = str(link["ac_lineage_key"])
        else:
            spec_type = "FEATURE_SPEC"
            spec_ref_id = spec.id
            spec_lineage_key = spec_lineage
        relation = SpecCodeLinkRelation(str(link.get("relation", "VERIFIES")))
        session.add(
            SpecCodeLink(
                project_id=project.id,
                repository_id=repo.id,
                spec_type=spec_type,
                spec_id=spec_ref_id,
                spec_lineage_key=spec_lineage_key,
                code_stable_key=str(link["code_stable_key"]),
                relation=relation,
                origin=SpecCodeLinkOrigin.HUMAN_CONFIRMED,
                confidence=1.0,
                established_index_version_id=version.id,
                last_confirmed_index_version_id=version.id,
                status=SpecCodeLinkStatus.ACTIVE,
            )
        )
    await session.flush()

    baseline_ids: list[uuid.UUID] = []
    for bl_cfg in cfg.get("baselines") or []:
        ac_lineage = str(bl_cfg.get("ac_lineage_key", ""))
        bl = BehavioralBaseline(
            project_id=project.id,
            lineage_key=str(bl_cfg["lineage_key"]),
            version=1,
            status=BaselineStatus.ACTIVE,
            source=BaselineSource.BROWNFIELD_EXISTING_TEST,
            given=str(bl_cfg.get("given", "Given")),
            when=str(bl_cfg.get("when", "When")),
            then=str(bl_cfg.get("then", "Then")),
            check_kind=BaselineCheckKind.EXISTING_TEST,
            check_ref=str(bl_cfg["check_ref"]),
            feature_spec_id=spec.id,
            ac_lineage_key=ac_lineage or None,
            observed_behavior_ids=[],
            exercised_stable_keys=[],
            established_sha=sha,
            established_evidence_id=None,
            activation=BaselineActivation.HUMAN,
        )
        session.add(bl)
        await session.flush()
        baseline_ids.append(bl.id)

    bset_key = str(cfg.get("baseline_set_key", "B1"))
    content = {"baseline_ids": [str(b) for b in baseline_ids], "commit_sha": sha}
    bset = BaselineSet(
        project_id=project.id,
        key=bset_key,
        commit_sha=sha,
        content_hash=sha256_hex(content),
        delivery_cycle_id=r1_cycle.id,
    )
    session.add(bset)
    await session.flush()
    for bid in baseline_ids:
        session.add(BaselineSetItem(baseline_set_id=bset.id, baseline_id=bid))

    project.readiness_state = ProjectReadiness.READY_FOR_CHANGE
    project.active_baseline_set_id = bset.id
    await session.flush()

    return TrustedProjectSeed(
        project_id=project.id,
        repository_id=repo.id,
        commit_sha=sha,
        index_version_id=version.id,
        feature_id=feature.id,
        feature_spec_id=spec.id,
        implementation_spec_id=impl.id,
        baseline_set_id=bset.id,
        ac_by_key=ac_by_key,
    )


async def seed_trusted_project_default(
    session: AsyncSession,
    ctx: CommandContext,
) -> TrustedProjectSeed:
    return await seed_trusted_project(session, SUPPORTDESK_R1, DEFAULT_SEED, ctx)
