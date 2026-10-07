"""Release manifest builder and validation."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.models import Finding, Gate
from core.commands.context import CommandContext
from core.domain.approvals.models import Approval
from core.domain.candidate_commits.models import CandidateCommit
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalStatus, SpecStatus
from core.domain.executions.models import Execution
from core.domain.projects.models import Project
from core.domain.repositories.models import Repository, RepositoryRevision
from core.domain.task_contracts.schemas import VersionedRef
from core.integration.enums import FindingStatus
from core.integration.models import IntegrationCandidate, IntegrationCandidateCommit
from core.intelligence.code_index.models import CodeIndexVersion
from core.planning.models import Architecture, ImplementationSpec
from core.policy.policy_service import get_cached_policy_content
from core.product_model.models import AcceptanceCriterion, FeatureSpec
from core.release.models import ReleaseManifest
from core.release.schemas import ReleaseManifestContent
from core.traceability.models import RepositoryIndexPointer


class ManifestBuilder:
    async def load_manifest(
        self, session: AsyncSession, manifest_id: uuid.UUID
    ) -> ReleaseManifest | None:
        return await session.get(ReleaseManifest, manifest_id)

    async def build_draft(
        self,
        session: AsyncSession,
        release_key: str,
        cycle: DeliveryCycle,
        ic: IntegrationCandidate,
        ctx: CommandContext,
    ) -> tuple[ReleaseManifestContent, str]:
        project = await session.get(Project, cycle.project_id)
        repo = await session.get(Repository, ic.repository_id)
        if project is None or repo is None or ic.integrated_sha is None:
            raise ValueError("missing project/repo/ic sha")
        pointer = await session.get(RepositoryIndexPointer, repo.id)
        canon_version_id = (
            pointer.canonical_index_version_id
            if pointer and pointer.canonical_index_version_id
            else ic.canonical_index_version_id
        )
        if canon_version_id is None:
            raise ValueError("canonical index missing")
        canon_version = await session.get(CodeIndexVersion, canon_version_id)
        if canon_version is None:
            raise ValueError("canonical index version missing")
        seq_result = await session.execute(
            select(RepositoryRevision.sequence)
            .where(RepositoryRevision.repository_id == repo.id)
            .order_by(RepositoryRevision.sequence.desc())
            .limit(1)
        )
        rev_seq = seq_result.scalar_one_or_none() or 0
        feature_specs: list[VersionedRef] = []
        impl_specs: list[VersionedRef] = []
        specs = await session.execute(
            select(FeatureSpec).where(
                FeatureSpec.project_id == cycle.project_id,
                FeatureSpec.status == SpecStatus.APPROVED,
            )
        )
        for spec in specs.scalars():
            feature_specs.append(
                VersionedRef(
                    ref_type="FEATURE_SPEC",
                    ref_id=spec.id,
                    version=spec.version,
                    key=spec.lineage_key,
                )
            )
        impl_rows = await session.execute(
            select(ImplementationSpec).where(
                ImplementationSpec.project_id == cycle.project_id,
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
        )
        for impl in impl_rows.scalars():
            impl_specs.append(
                VersionedRef(
                    ref_type="IMPLEMENTATION_SPEC",
                    ref_id=impl.id,
                    version=impl.version,
                    key=impl.lineage_key,
                )
            )
        arch: VersionedRef | None = None
        arch_row = await session.execute(
            select(Architecture)
            .where(
                Architecture.project_id == cycle.project_id,
                Architecture.status == SpecStatus.APPROVED,
            )
            .order_by(Architecture.version.desc())
            .limit(1)
        )
        ar = arch_row.scalar_one_or_none()
        if ar is not None:
            arch = VersionedRef(
                ref_type="ARCHITECTURE",
                ref_id=ar.id,
                version=ar.version,
                key=ar.lineage_key,
            )
        acceptance: list[dict[str, object]] = []
        spec_ids = [ref.ref_id for ref in feature_specs]
        if spec_ids:
            ac_rows = await session.execute(
                select(AcceptanceCriterion).where(AcceptanceCriterion.feature_spec_id.in_(spec_ids))
            )
            for ac in ac_rows.scalars():
                acceptance.append(
                    {
                        "ac_key": ac.lineage_key,
                        "mandatory": ac.mandatory,
                        "evidence": [],
                        "status": "UNKNOWN",
                    }
                )
        gates_rows = await session.execute(
            select(Gate).where(Gate.integration_candidate_id == ic.id)
        )
        gates = {g.gate_type.value: g.status.value for g in gates_rows.scalars()}
        approvals = await session.execute(
            select(Approval.key).where(
                Approval.delivery_cycle_id == cycle.id,
                Approval.status == ApprovalStatus.APPROVED,
            )
        )
        waived = await session.execute(
            select(Finding.key).where(
                Finding.delivery_cycle_id == cycle.id,
                Finding.status == FindingStatus.WAIVED,
            )
        )
        blocking_count = len(
            (
                await session.execute(
                    select(Finding.id).where(
                        Finding.delivery_cycle_id == cycle.id,
                        Finding.blocking.is_(True),
                        Finding.status.in_([FindingStatus.OPEN, FindingStatus.IN_REMEDIATION]),
                    )
                )
            )
            .scalars()
            .all()
        )
        ic_commits = await session.execute(
            select(IntegrationCandidateCommit.candidate_commit_id).where(
                IntegrationCandidateCommit.integration_candidate_id == ic.id
            )
        )
        cc_ids = list(ic_commits.scalars())
        exec_keys: list[str] = []
        cc_keys: list[str] = []
        if cc_ids:
            ccs = await session.execute(
                select(CandidateCommit).where(CandidateCommit.id.in_(cc_ids))
            )
            for cc in ccs.scalars():
                cc_keys.append(cc.key)
                if cc.execution_id:
                    ex = await session.get(Execution, cc.execution_id)
                    if ex:
                        exec_keys.append(ex.key)
        policy = get_cached_policy_content()
        content = ReleaseManifestContent(
            release_key=release_key,
            project_key=project.key,
            delivery_cycle_key=cycle.key,
            cycle_type=cycle.type.value,
            repository={
                "repository_id": str(repo.id),
                "name": repo.name,
                "source_type": repo.source_type.value,
                "provider": repo.provider.value,
                "remote_url": repo.remote_url,
                "default_branch": repo.default_branch,
                "canonical_commit": repo.canonical_commit,
                "canonical_revision_sequence": rev_seq,
            },
            integration_candidate={
                "key": ic.key,
                "integrated_sha": ic.integrated_sha,
                "base_sha": ic.base_sha,
            },
            canonical_index_version_id=canon_version.id,
            canonical_index_hash=canon_version.content_hash or "",
            feature_specs=feature_specs,
            implementation_specs=impl_specs,
            architecture=arch,
            acceptance=acceptance,
            gates=gates,
            approvals=list(approvals.scalars()),
            waived_findings=list(waived.scalars()),
            blocking_findings=blocking_count,
            executions=exec_keys,
            candidate_commits=cc_keys,
            policy_version=str(policy.get("version", 1)),
        )
        content_hash = sha256_hex(content.model_dump(mode="json"))
        return content, content_hash

    async def persist(
        self,
        session: AsyncSession,
        release_id: uuid.UUID,
        content: ReleaseManifestContent,
        content_hash: str,
    ) -> ReleaseManifest:
        row = ReleaseManifest(
            release_id=release_id,
            content=content.model_dump(mode="json"),
            content_hash=content_hash,
        )
        session.add(row)
        await session.flush()
        return row


def validate_manifest_against_ic(
    content: ReleaseManifestContent,
    ic: IntegrationCandidate,
    cycle: DeliveryCycle,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if content.integration_candidate.get("integrated_sha") != ic.integrated_sha:
        reasons.append("MANIFEST_IC_SHA_MISMATCH")
    if ic.integrated_sha and content.repository.get("canonical_commit") != ic.integrated_sha:
        reasons.append("MANIFEST_CANONICAL_MISMATCH")
    if content.delivery_cycle_key != cycle.key:
        reasons.append("MANIFEST_CYCLE_MISMATCH")
    if ic.status.value != "READY":
        reasons.append("IC_NOT_READY")
    return not reasons, reasons
