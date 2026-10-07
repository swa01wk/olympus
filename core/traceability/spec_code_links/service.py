"""SpecCodeLink materialization from integration lineage."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from core.domain.delivery_cycles.models import DeliveryCycle
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.findings import FindingService
from core.commands.context import CommandContext
from core.domain.candidate_commits.models import CandidateCommit
from core.domain.events.append import append_domain_event
from core.integration.enums import (
    FindingSeverity,
    FindingSource,
    SpecCodeLinkOrigin,
    SpecCodeLinkRelation,
    SpecCodeLinkStatus,
)
from core.integration.models import IntegrationCandidate
from core.intelligence.code_index.models import CodeEntity
from core.planning.models import TaskSpecRef
from core.traceability.models import CodeEntityChange, SpecCodeLink
from core.traceability.spec_code_links.principal import is_principal_entity


def _resolve_test_entity(entity_by_key: dict[str, CodeEntity], test_ref: str) -> CodeEntity | None:
    if test_ref in entity_by_key:
        return entity_by_key[test_ref]
    for entity in entity_by_key.values():
        if entity.qualified_name == test_ref or entity.qualified_name.endswith(f".{test_ref}"):
            return entity
    return None


class SpecCodeLinkService:
    async def materialize_generated(
        self,
        session: AsyncSession,
        ic_id: uuid.UUID,
        canonical_index_version_id: uuid.UUID,
        ctx: CommandContext,
    ) -> list[SpecCodeLink]:
        ic = await session.get(IntegrationCandidate, ic_id)
        if ic is None:
            return []
        from core.domain.delivery_cycles.models import DeliveryCycle

        cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
        if cycle is None:
            return []
        entities = await session.execute(
            select(CodeEntity).where(CodeEntity.index_version_id == canonical_index_version_id)
        )
        entity_by_key = {e.stable_key: e for e in entities.scalars()}
        change_rows = list(
            (
                await session.execute(
                    select(CodeEntityChange).where(
                        CodeEntityChange.integration_candidate_id == ic_id
                    )
                )
            ).scalars()
        )
        links: list[SpecCodeLink] = []
        for change in change_rows:
            entity = entity_by_key.get(change.stable_key)
            if entity is None:
                continue
            cc = await session.execute(
                select(CandidateCommit).where(
                    CandidateCommit.task_id == change.task_id,
                    CandidateCommit.sha == change.candidate_commit_sha,
                )
            )
            commit = cc.scalar_one_or_none()
            declared = set(commit.principal_symbols_declared if commit else [])
            if not is_principal_entity(entity, declared):
                continue
            spec_refs = await session.execute(
                select(TaskSpecRef).where(TaskSpecRef.task_id == change.task_id)
            )
            for ref in spec_refs.scalars():
                if ref.ref_type not in ("IMPLEMENTATION_SPEC", "FEATURE_SPEC"):
                    continue
                lineage_key = await self._lineage_key_for_spec(
                    session, ref.ref_type, ref.ref_id, ref.ref_version
                )
                link = SpecCodeLink(
                    project_id=cycle.project_id,
                    repository_id=ic.repository_id,
                    spec_type=ref.ref_type,
                    spec_id=ref.ref_id,
                    spec_lineage_key=lineage_key,
                    code_stable_key=change.stable_key,
                    relation=SpecCodeLinkRelation.IMPLEMENTS,
                    origin=SpecCodeLinkOrigin.GENERATED_LINEAGE,
                    confidence=1.0,
                    task_id=change.task_id,
                    execution_id=change.execution_id,
                    commit_sha=change.candidate_commit_sha,
                    evidence_refs=[],
                    established_index_version_id=canonical_index_version_id,
                    last_confirmed_index_version_id=canonical_index_version_id,
                    status=SpecCodeLinkStatus.ACTIVE,
                )
                session.add(link)
                links.append(link)
            if commit and commit.principal_symbols_declared:
                for sym in commit.principal_symbols_declared:
                    if sym not in entity_by_key and not any(
                        e.qualified_name.endswith(sym) for e in entity_by_key.values()
                    ):
                        await FindingService().create(
                            session,
                            project_id=cycle.project_id,
                            delivery_cycle_id=cycle.id,
                            source=FindingSource.LINEAGE,
                            category="LINEAGE_DECLARATION_MISMATCH",
                            severity=FindingSeverity.MINOR,
                            title=f"Declared principal symbol missing from index: {sym}",
                            detail={"symbol": sym, "task_id": str(change.task_id)},
                            ctx=ctx,
                            integration_candidate_id=ic.id,
                        )
        verify_links = await self._materialize_verifies(
            session,
            ic=ic,
            cycle=cycle,
            canonical_index_version_id=canonical_index_version_id,
            entity_by_key=entity_by_key,
            ctx=ctx,
        )
        links.extend(verify_links)
        await session.flush()
        for link in links:
            await append_domain_event(
                session,
                aggregate_type="spec_code_link",
                aggregate_id=link.id,
                event_type="spec_code_link.created",
                payload={"spec_lineage_key": link.spec_lineage_key, "origin": link.origin.value},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
                project_id=cycle.project_id,
                delivery_cycle_id=cycle.id,
            )
        return links

    async def _materialize_verifies(
        self,
        session: AsyncSession,
        *,
        ic: IntegrationCandidate,
        cycle: DeliveryCycle,
        canonical_index_version_id: uuid.UUID,
        entity_by_key: dict[str, CodeEntity],
        ctx: CommandContext,
    ) -> list[SpecCodeLink]:
        from agents.forge.schemas import ImplementationResult

        from core.domain.executions.models import Execution
        from core.integration.models import IntegrationCandidateCommit
        from core.intelligence.code_index.enums import EntityType
        from core.product_model.models import AcceptanceCriterion, FeatureSpec

        links: list[SpecCodeLink] = []
        task_commits: dict[uuid.UUID, CandidateCommit] = {}
        ic_links = await session.execute(
            select(IntegrationCandidateCommit).where(
                IntegrationCandidateCommit.integration_candidate_id == ic.id,
                IntegrationCandidateCommit.included.is_(True),
            )
        )
        for ic_link in ic_links.scalars():
            cc = await session.get(CandidateCommit, ic_link.candidate_commit_id)
            if cc is not None:
                task_commits[cc.task_id] = cc

        for task_id, cc in task_commits.items():
            execution = await session.get(Execution, cc.execution_id)
            if execution is None or execution.output is None:
                continue
            try:
                impl = ImplementationResult.model_validate(execution.output)
            except Exception:
                continue
            if not impl.ac_test_mapping:
                continue
            feature_spec_ids = await self._feature_spec_ids_for_task(session, task_id)

            for entry in impl.ac_test_mapping:
                test_entity = _resolve_test_entity(entity_by_key, entry.test_ref)
                if test_entity is None or test_entity.type != EntityType.TEST:
                    continue
                ac_query = (
                    select(AcceptanceCriterion)
                    .join(
                        FeatureSpec,
                        AcceptanceCriterion.feature_spec_id == FeatureSpec.id,
                    )
                    .where(
                        FeatureSpec.project_id == cycle.project_id,
                        AcceptanceCriterion.lineage_key == entry.ac_ref,
                    )
                )
                if feature_spec_ids:
                    ac_query = ac_query.where(
                        AcceptanceCriterion.feature_spec_id.in_(feature_spec_ids)
                    )
                ac = (await session.execute(ac_query)).scalar_one_or_none()
                if ac is None:
                    continue
                spec_link = SpecCodeLink(
                    project_id=cycle.project_id,
                    repository_id=ic.repository_id,
                    spec_type="ACCEPTANCE_CRITERION",
                    spec_id=ac.id,
                    spec_lineage_key=ac.lineage_key,
                    code_stable_key=test_entity.stable_key,
                    relation=SpecCodeLinkRelation.VERIFIES,
                    origin=SpecCodeLinkOrigin.GENERATED_LINEAGE,
                    confidence=1.0,
                    task_id=task_id,
                    execution_id=cc.execution_id,
                    commit_sha=cc.sha,
                    evidence_refs=[],
                    established_index_version_id=canonical_index_version_id,
                    last_confirmed_index_version_id=canonical_index_version_id,
                    status=SpecCodeLinkStatus.ACTIVE,
                )
                session.add(spec_link)
                links.append(spec_link)
        return links

    async def _feature_spec_ids_for_task(
        self, session: AsyncSession, task_id: uuid.UUID
    ) -> list[uuid.UUID]:
        from core.domain.tasks.models import Task
        from core.planning.models import ImplementationSpec, TaskSpecRef

        ids: list[uuid.UUID] = []
        task_row = await session.get(Task, task_id)
        if task_row is not None and task_row.implementation_spec_id is not None:
            impl = await session.get(ImplementationSpec, task_row.implementation_spec_id)
            if impl is not None:
                ids.append(impl.feature_spec_id)
        spec_refs = await session.execute(select(TaskSpecRef).where(TaskSpecRef.task_id == task_id))
        for ref in spec_refs.scalars():
            if ref.ref_type == "FEATURE_SPEC":
                ids.append(ref.ref_id)
            elif ref.ref_type == "IMPLEMENTATION_SPEC":
                impl = await session.get(ImplementationSpec, ref.ref_id)
                if impl is not None:
                    ids.append(impl.feature_spec_id)
        seen: set[uuid.UUID] = set()
        out: list[uuid.UUID] = []
        for spec_id in ids:
            if spec_id not in seen:
                seen.add(spec_id)
                out.append(spec_id)
        return out

    async def _feature_spec_id_for_task(
        self, session: AsyncSession, task_id: uuid.UUID
    ) -> uuid.UUID | None:
        ids = await self._feature_spec_ids_for_task(session, task_id)
        return ids[0] if ids else None

    async def _lineage_key_for_spec(
        self,
        session: AsyncSession,
        spec_type: str,
        spec_id: uuid.UUID,
        version: int | None,
    ) -> str:
        if spec_type == "IMPLEMENTATION_SPEC":
            from core.planning.models import ImplementationSpec

            row = await session.get(ImplementationSpec, spec_id)
            if row is not None:
                return row.lineage_key
        if spec_type == "FEATURE_SPEC":
            from core.product_model.models import FeatureSpec

            feature_row = await session.get(FeatureSpec, spec_id)
            if feature_row is not None:
                return feature_row.lineage_key
        if spec_type == "ACCEPTANCE_CRITERION":
            from core.product_model.models import AcceptanceCriterion

            ac = await session.get(AcceptanceCriterion, spec_id)
            if ac is not None:
                return ac.lineage_key
        return f"{spec_type}:{spec_id}"

    async def links_for_spec(
        self,
        session: AsyncSession,
        lineage_key: str,
        status: SpecCodeLinkStatus = SpecCodeLinkStatus.ACTIVE,
    ) -> list[SpecCodeLink]:
        result = await session.execute(
            select(SpecCodeLink).where(
                SpecCodeLink.spec_lineage_key == lineage_key,
                SpecCodeLink.status == status,
            )
        )
        return list(result.scalars())

    async def links_for_entity(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        stable_key: str,
        status: str = "ACTIVE",
    ) -> list[SpecCodeLink]:
        result = await session.execute(
            select(SpecCodeLink).where(
                SpecCodeLink.repository_id == repository_id,
                SpecCodeLink.code_stable_key == stable_key,
                SpecCodeLink.status == status,
            )
        )
        return list(result.scalars())
