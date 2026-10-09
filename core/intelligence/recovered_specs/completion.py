from __future__ import annotations

import uuid
from typing import Any

from agents.scout.schemas import RecoveredFeatureSpec, RepositorySurvey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.executions.models import Execution
from core.intelligence.brownfield.models import ObservedBehavior
from core.intelligence.recovered_specs.context import ScoutContextBuilder
from core.intelligence.recovered_specs.orchestrator import BrownfieldOrchestrator
from core.intelligence.recovered_specs.service import RecoveryService
from core.intelligence.recovered_specs.validation import RecoveryValidator, discovery_fact_aliases
from core.product_model.models import KnowledgeItem
from core.traceability.models import RepositoryIndexPointer


async def _principal_aliases(
    session: AsyncSession, index_version_id: uuid.UUID
) -> dict[str, list[str]]:
    """Handler and test keys -> the ROUTE that exposes / is verified by them."""
    from sqlalchemy.orm import aliased

    from core.intelligence.code_index.enums import EntityType, RelationType
    from core.intelligence.code_index.models import CodeEntity, CodeRelation

    src = aliased(CodeEntity)
    tgt = aliased(CodeEntity)
    rows = (
        await session.execute(
            select(src.stable_key, tgt.stable_key)
            .join(CodeRelation, CodeRelation.source_entity_id == src.id)
            .join(tgt, CodeRelation.target_entity_id == tgt.id)
            .where(
                CodeRelation.index_version_id == index_version_id,
                CodeRelation.relation.in_((RelationType.EXPOSES, RelationType.VERIFIED_BY)),
                src.type == EntityType.ROUTE,
            )
        )
    ).all()
    aliases: dict[str, list[str]] = {}
    for route_key, target_key in rows:
        aliases.setdefault(target_key, []).append(route_key)
    return aliases


class BrownfieldCompletionService:
    async def after_existing_tests(
        self,
        session: AsyncSession,
        execution: Execution,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
        if cycle is None or cycle.base_sha is None:
            return
        pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
        if pointer is None or pointer.canonical_index_version_id is None:
            return
        from core.intelligence.recovered_specs.observed import ObservedBehaviorService

        await ObservedBehaviorService().derive(
            session,
            delivery_cycle_id=cycle.id,
            project_id=cycle.project_id,
            index_version_id=pointer.canonical_index_version_id,
            commit_sha=cycle.base_sha,
            test_results=output,
            ctx=ctx,
        )
        await BrownfieldOrchestrator().schedule_survey(session, cycle.id, ctx)

    async def persist_from_execution(
        self,
        session: AsyncSession,
        execution: Execution,
        profile: str,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        if profile == "scout.survey":
            await self._after_survey(session, execution, output, ctx)
        elif profile == "scout.recover_feature":
            await self._store_feature_draft(session, execution, output)

    async def _store_feature_draft(
        self,
        session: AsyncSession,
        execution: Execution,
        output: dict[str, Any],
    ) -> None:
        execution.output = {**(execution.output or {}), "recovered_feature": output}
        await session.flush()

    async def _after_survey(
        self,
        session: AsyncSession,
        execution: Execution,
        output: dict[str, Any],
        ctx: CommandContext,
    ) -> None:
        survey = RepositorySurvey.model_validate(output)
        cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
        if cycle is None:
            return
        feature_refs = [f.ref for f in survey.features]
        await BrownfieldOrchestrator().schedule_recover_feature_tasks(
            session, cycle.id, feature_refs, execution.task_id, ctx
        )
        execution.output = {**(execution.output or {}), "survey": output}
        await session.flush()

    async def try_finalize_recovery(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        from core.domain.enums import TaskStatus
        from core.domain.tasks.models import Task

        pending = (
            (
                await session.execute(
                    select(Task).where(
                        Task.delivery_cycle_id == cycle_id,
                        Task.status.notin_(
                            [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        scout_pending = [
            t for t in pending if t.title.startswith("Recover feature") or "Scout" in t.title
        ]
        if scout_pending:
            return
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            return
        from core.intelligence.brownfield.enums import RecoveryProposalStatus
        from core.intelligence.brownfield.models import RecoveryProposal

        prior = (
            await session.execute(
                select(
                    RecoveryProposal.status,
                    RecoveryProposal.survey_execution_id,
                    RecoveryProposal.validation_report,
                ).where(RecoveryProposal.delivery_cycle_id == cycle_id)
            )
        ).all()
        if any(p.status != RecoveryProposalStatus.REJECTED for p in prior):
            return
        # A retry re-runs Scout; outputs consumed by a rejected attempt must not mix in.
        consumed: set[str] = set()
        for p in prior:
            if p.survey_execution_id is not None:
                consumed.add(str(p.survey_execution_id))
            consumed.update((p.validation_report or {}).get("consumed_execution_ids", []))
        survey_exec = [
            ex
            for ex in (
                await session.execute(
                    select(Execution)
                    .where(Execution.delivery_cycle_id == cycle_id, Execution.output.isnot(None))
                    .order_by(Execution.created_at)
                )
            )
            .scalars()
            .all()
            if str(ex.id) not in consumed
        ]
        survey_output = None
        survey_execution_id = None
        feature_outputs: list[tuple[uuid.UUID, RecoveredFeatureSpec]] = []
        for ex in survey_exec:
            if ex.output is None:
                continue
            if ex.output.get("survey"):
                survey_output = ex.output["survey"]
                survey_execution_id = ex.id
            elif ex.output.get("features") and ex.output.get("recovered_architecture"):
                survey_output = ex.output
                survey_execution_id = ex.id
            if ex.output.get("recovered_feature"):
                feature_outputs.append(
                    (ex.id, RecoveredFeatureSpec.model_validate(ex.output["recovered_feature"]))
                )
            elif ex.output.get("feature_ref") and ex.output.get("body"):
                feature_outputs.append((ex.id, RecoveredFeatureSpec.model_validate(ex.output)))
        if survey_output is None or survey_execution_id is None or not feature_outputs:
            return
        survey = RepositorySurvey.model_validate(survey_output)
        behaviors = (
            (
                await session.execute(
                    select(ObservedBehavior).where(ObservedBehavior.delivery_cycle_id == cycle_id)
                )
            )
            .scalars()
            .all()
        )
        behavior_ids = {b.key for b in behaviors}
        behavior_kinds = {b.key: b.kind.value for b in behaviors}
        facts = (
            (
                await session.execute(
                    select(KnowledgeItem).where(KnowledgeItem.delivery_cycle_id == cycle_id)
                )
            )
            .scalars()
            .all()
        )
        fact_ids = {str(f.id) for f in facts}
        fact_statements = {f.statement for f in facts if f.statement}
        for stmt in fact_statements:
            fact_ids.add(stmt)
        fact_ids.update(discovery_fact_aliases(fact_statements))
        entity_keys: set[str] = set()
        for b in behaviors:
            entity_keys.update(str(k) for k in b.subject_stable_keys)
        principal_aliases: dict[str, list[str]] = {}
        pointer = await session.get(RepositoryIndexPointer, cycle.repository_id)
        if pointer and pointer.canonical_index_version_id:
            from core.intelligence.code_index.models import CodeEntity

            index_entities = (
                await session.execute(
                    select(CodeEntity).where(
                        CodeEntity.index_version_id == pointer.canonical_index_version_id
                    )
                )
            ).scalars()
            entity_keys.update(e.stable_key for e in index_entities)
            principal_aliases = await _principal_aliases(
                session, pointer.canonical_index_version_id
            )
        consumed_ids = [str(survey_execution_id)] + [str(fo[0]) for fo in feature_outputs]
        validator = RecoveryValidator()
        exec_by_ref = {spec.feature_ref: exec_id for exec_id, spec in feature_outputs}
        survey, kept_specs, pruned = validator.prune_unsupported(
            survey,
            [fo[1] for fo in feature_outputs],
            behavior_ids=behavior_ids,
            fact_ids=fact_ids,
            fact_statements=fact_statements,
            entity_keys=entity_keys,
            principal_aliases=principal_aliases,
        )
        feature_outputs = [(exec_by_ref[s.feature_ref], s) for s in kept_specs]
        ok, errors = validator.validate_survey(
            survey,
            behavior_ids=behavior_ids,
            fact_ids=fact_ids,
            fact_statements=fact_statements,
            entity_keys=entity_keys,
        )
        if not feature_outputs:
            ok = False
            errors.append("NO_SUPPORTED_FEATURES")
        feature_reports: dict[str, Any] = {}
        for spec in [fo[1] for fo in feature_outputs]:
            fok, ferr, report = validator.validate_feature_spec(
                spec,
                behavior_ids=behavior_ids,
                fact_ids=fact_ids,
                fact_statements=fact_statements,
                entity_keys=entity_keys,
                behavior_kinds=behavior_kinds,
            )
            ok = ok and fok
            errors.extend(ferr)
            feature_reports[spec.feature_ref] = report
        report_body: dict[str, Any] = {
            "errors": errors,
            "features": feature_reports,
            "pruned": pruned,
            "consumed_execution_ids": consumed_ids,
        }
        if not ok:
            session.add(
                RecoveryProposal(
                    delivery_cycle_id=cycle_id,
                    survey_execution_id=survey_execution_id,
                    feature_execution_ids=[str(fo[0]) for fo in feature_outputs],
                    status=RecoveryProposalStatus.REJECTED,
                    validation_report=report_body,
                    context_manifest_hash="",
                )
            )
            await session.flush()
            return
        _, manifest_hash = await ScoutContextBuilder().build(session, cycle_id)
        assert cycle.repository_id is not None
        repository_id = cycle.repository_id
        pointer = await session.get(RepositoryIndexPointer, repository_id)
        assert pointer and pointer.canonical_index_version_id
        await RecoveryService().persist(
            session,
            delivery_cycle_id=cycle_id,
            project_id=cycle.project_id,
            survey=survey,
            feature_specs=[fo[1] for fo in feature_outputs],
            survey_execution_id=survey_execution_id,
            feature_execution_ids=[fo[0] for fo in feature_outputs],
            context_manifest_hash=manifest_hash,
            validation_report=report_body,
            ctx=ctx,
            repository_id=repository_id,
            index_version_id=pointer.canonical_index_version_id,
            commit_sha=cycle.base_sha or "",
        )
