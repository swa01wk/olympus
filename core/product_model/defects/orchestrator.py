"""Bug-fix cycle task scheduling."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskContractStatus, TaskOrigin, WorkType
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.tasks.service import TaskService
from core.product_model.defects.reproduction_context import build_reproduction_snapshot
from core.product_model.defects.service import DefectService
from core.review.context import RevisionContext
from core.review.contract_snapshot import attach_snapshot


class BugFixOrchestrator:
    async def schedule_defect_triage(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> dict[str, str]:
        context = await DefectService().build_triage_context(session, cycle_id)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Triage defect",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Triage defect against product model",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=cycle_id)],
            repository_id=cycle.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="kira.defect_triage",
            model_alias="product_decomposition",
            required_outputs=["artifact:DEFECT_TRIAGE"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body={**body.model_dump(mode="json"), "_snapshot": context},
            content_hash=sha256_hex(f"defect-triage-{cycle_id}"),
            compiled_by="bug_fix",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"triage_task_id": str(task.id)}

    async def schedule_reproduce(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> dict[str, str]:
        defect = await DefectService().get_by_cycle(session, cycle_id)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if defect is None or cycle is None:
            raise ValueError("defect/cycle missing")
        snapshot = await build_reproduction_snapshot(session, cycle, defect)
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Author reproduction test",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Author pytest reproduction for defect",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DEFECT", ref_id=defect.id)],
            repository_id=cycle.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="sentinel.reproduce",
            model_alias="verification_planning",
            required_outputs=["artifact:REPRODUCTION_TEST"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body={**body.model_dump(mode="json"), "_snapshot": snapshot},
            content_hash=sha256_hex(f"sentinel-reproduce-{cycle_id}"),
            compiled_by="bug_fix",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"reproduce_task_id": str(task.id)}

    async def schedule_reproduction_run(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        artifact_id: uuid.UUID,
        ctx: CommandContext,
    ) -> dict[str, str]:
        defect = await DefectService().get_by_cycle(session, cycle_id)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if defect is None or cycle is None:
            raise ValueError("defect/cycle missing")
        triage = defect.triage or {}
        signature = triage.get("observed_symptom_signature") or {}
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Run reproduction test",
            WorkType.VERIFICATION,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Execute reproduction test at affected SHA",
            work_type=WorkType.VERIFICATION,
            inputs=[VersionedRef(ref_type="DEFECT", ref_id=defect.id)],
            repository_id=cycle.repository_id,
            executor_kind="DETERMINISTIC",
            deterministic_executor="reproduction.run",
            required_outputs=[],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body={
                **body.model_dump(mode="json"),
                "defect_id": str(defect.id),
                "phase": "PRE_REPAIR",
                "artifact_id": str(artifact_id),
                "commit_sha": defect.affected_sha,
                "observed_symptom_signature": signature,
                "entry_route_key": "ROUTE:PATCH /tickets/{ticket_id}",
                "stability_runs": 2,
            },
            content_hash=sha256_hex(f"reproduction-run-{cycle_id}-{artifact_id}"),
            compiled_by="bug_fix",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"reproduction_run_task_id": str(task.id)}

    async def schedule_expected_behavior(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        revision: RevisionContext | None = None,
    ) -> dict[str, str]:
        defect = await DefectService().get_by_cycle(session, cycle_id)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if defect is None or cycle is None:
            raise ValueError("defect/cycle missing")
        citations = await DefectService().approved_ac_citations(session, defect)
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Resolve expected behavior",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Map defect to intended behavior",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DEFECT", ref_id=defect.id)],
            repository_id=cycle.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="kira.expected_behavior",
            model_alias="product_decomposition",
            required_outputs=["artifact:EXPECTED_BEHAVIOR"],
        )
        snapshot = {
            "defect_description": defect.description,
            "triage_json": json.dumps(defect.triage or {}, indent=2),
            "approved_acs_json": json.dumps(citations, indent=2),
        }
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=attach_snapshot(
                body.model_dump(mode="json"), snapshot=snapshot, revision=revision
            ),
            content_hash=sha256_hex(f"expected-behavior-{cycle_id}"),
            compiled_by="bug_fix",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"expected_behavior_task_id": str(task.id), "task_id": str(task.id)}

    async def schedule_root_cause(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> dict[str, str]:
        from sqlalchemy import select

        from core.product_model.defects.models import Reproduction, TraceCorrelation

        defect = await DefectService().get_by_cycle(session, cycle_id)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if defect is None or cycle is None:
            raise ValueError("defect/cycle missing")

        trace = (
            await session.execute(
                select(TraceCorrelation)
                .join(Reproduction, TraceCorrelation.reproduction_id == Reproduction.id)
                .where(Reproduction.defect_id == defect.id)
                .order_by(TraceCorrelation.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Root cause analysis",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Hypothesize root cause from trace and code",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DEFECT", ref_id=defect.id)],
            repository_id=cycle.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="warden.root_cause",
            model_alias="review",
            required_outputs=["artifact:ROOT_CAUSE"],
        )
        candidates = trace.candidates if trace else []
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body={
                **body.model_dump(mode="json"),
                "_snapshot": {
                    "candidates_json": json.dumps(candidates, indent=2),
                    "trace_correlation_id": str(trace.id) if trace else "",
                },
            },
            content_hash=sha256_hex(f"root-cause-{cycle_id}"),
            compiled_by="bug_fix",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"root_cause_task_id": str(task.id)}

    async def schedule_reproduction_run_post(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        artifact_id: uuid.UUID,
        commit_sha: str,
        ctx: CommandContext,
    ) -> dict[str, str]:
        defect = await DefectService().get_by_cycle(session, cycle_id)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if defect is None or cycle is None:
            raise ValueError("defect/cycle missing")
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Post-repair reproduction",
            WorkType.VERIFICATION,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Verify original reproduction passes at IC SHA",
            work_type=WorkType.VERIFICATION,
            inputs=[VersionedRef(ref_type="DEFECT", ref_id=defect.id)],
            repository_id=cycle.repository_id,
            executor_kind="DETERMINISTIC",
            deterministic_executor="reproduction.run",
            required_outputs=[],
        )
        from core.integration.enums import ICStatus
        from core.integration.models import IntegrationCandidate

        ic_row = (
            await session.execute(
                select(IntegrationCandidate).where(
                    IntegrationCandidate.delivery_cycle_id == cycle_id,
                    IntegrationCandidate.status == ICStatus.READY,
                )
            )
        ).scalar_one_or_none()
        contract_body: dict[str, object] = {
            **body.model_dump(mode="json"),
            "defect_id": str(defect.id),
            "phase": "POST_REPAIR",
            "artifact_id": str(artifact_id),
            "commit_sha": commit_sha,
            "stability_runs": 1,
        }
        if ic_row is not None:
            contract_body["integration_candidate_id"] = str(ic_row.id)
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=contract_body,
            content_hash=sha256_hex(f"reproduction-post-{cycle_id}"),
            compiled_by="bug_fix",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"post_reproduction_task_id": str(task.id)}

    async def schedule_repair_implementation_spec(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        revision: RevisionContext | None = None,
    ) -> dict[str, str]:
        from core.domain.enums import SpecStatus
        from core.intelligence.impact.engine import ImpactEngine
        from core.policy.policy_service import get_cached_policy_content
        from core.product_model.defects.models import (
            ExpectedBehaviorResolution,
            Reproduction,
            RootCauseAnalysis,
        )
        from core.product_model.models import FeatureSpec

        defect = await DefectService().get_by_cycle(session, cycle_id)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if defect is None or cycle is None:
            raise ValueError("defect/cycle missing")
        fs_id: uuid.UUID | None = None
        if defect.linked_feature_ids:
            from core.product_model.models import Feature

            feat = await session.get(Feature, uuid.UUID(str(defect.linked_feature_ids[0])))
            if feat is not None:
                fs = (
                    await session.execute(
                        select(FeatureSpec)
                        .where(
                            FeatureSpec.feature_id == feat.id,
                            FeatureSpec.status == SpecStatus.APPROVED,
                        )
                        .order_by(FeatureSpec.version.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if fs is not None:
                    fs_id = fs.id
        if fs_id is None:
            fs = (
                await session.execute(
                    select(FeatureSpec)
                    .where(
                        FeatureSpec.project_id == cycle.project_id,
                        FeatureSpec.status == SpecStatus.APPROVED,
                    )
                    .order_by(FeatureSpec.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            fs_id = fs.id if fs else None
        if fs_id is None:
            raise ValueError("feature spec missing")

        rca = (
            await session.execute(
                select(RootCauseAnalysis)
                .where(RootCauseAnalysis.defect_id == defect.id)
                .order_by(RootCauseAnalysis.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        pre = (
            await session.execute(
                select(Reproduction)
                .where(
                    Reproduction.defect_id == defect.id,
                    Reproduction.phase == "PRE_REPAIR",
                )
                .order_by(Reproduction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        expected = (
            await session.execute(
                select(ExpectedBehaviorResolution)
                .where(ExpectedBehaviorResolution.defect_id == defect.id)
                .order_by(ExpectedBehaviorResolution.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        ia = await ImpactEngine().latest_complete(session, cycle_id)
        policy = get_cached_policy_content().get("bugfix", {})
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Draft REPAIR implementation spec",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        task.governing_ref_id = fs_id
        await session.flush()
        body = TaskContractBody(
            objective="Draft minimal REPAIR implementation spec",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="FEATURE_SPEC", ref_id=fs_id)],
            repository_id=cycle.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="kira.implementation_spec",
            model_alias="planning",
            required_outputs=["artifact:IMPLEMENTATION_SPEC_DRAFT"],
        )
        repair_snapshot = {
            "implementation_spec_mode": "REPAIR",
            "project_name": str(cycle.objective),
            "root_cause_summary": rca.explanation if rca else "",
            "root_cause_json": json.dumps(
                {
                    "faulty_stable_keys": rca.faulty_stable_keys,
                    "fix_outline": rca.fix_outline,
                    "regression_risks": rca.regression_risks,
                }
                if rca
                else {},
                indent=2,
            ),
            "expected_behavior": expected.statement if expected else "",
            "impact_assessment_json": json.dumps({"id": str(ia.id) if ia else None}, indent=2),
            "expected_ac_keys": ",".join(defect.expected_ac_ids or []),
            "reproduction_artifact_ref": str(pre.artifact_id) if pre else "",
            "max_repair_files": str(policy.get("max_repair_files", 3)),
        }
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=attach_snapshot(
                body.model_dump(mode="json"),
                snapshot=repair_snapshot,
                revision=revision,
            ),
            content_hash=sha256_hex(f"repair-impl-spec-{cycle_id}"),
            compiled_by="bug_fix",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"repair_implementation_spec_task_id": str(task.id)}

    async def schedule_repair_task_plan(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
        *,
        revision: RevisionContext | None = None,
    ) -> dict[str, str]:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            raise ValueError("cycle missing")
        task = await TaskService().create_task(
            session,
            cycle_id,
            "Generate REPAIR task plan",
            WorkType.ANALYSIS,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective="Generate REPAIR task plan with regression test",
            work_type=WorkType.ANALYSIS,
            inputs=[VersionedRef(ref_type="DELIVERY_CYCLE", ref_id=cycle_id)],
            repository_id=cycle.repository_id,
            executor_kind="AGENT_RUNTIME",
            agent_profile="kira.task_plan",
            model_alias="planning",
            required_outputs=["artifact:TASK_PLAN"],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body=attach_snapshot(body.model_dump(mode="json"), revision=revision),
            content_hash=sha256_hex(f"repair-task-plan-{cycle_id}"),
            compiled_by="bug_fix",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"repair_task_plan_task_id": str(task.id)}

    async def schedule_regression_test_run(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        regression_test_path: str,
        commit_sha: str,
        ctx: CommandContext,
        *,
        integration_candidate_id: uuid.UUID,
        validate_at_affected: bool = False,
    ) -> dict[str, str]:
        defect = await DefectService().get_by_cycle(session, cycle_id)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if defect is None or cycle is None:
            raise ValueError("defect/cycle missing")
        title = (
            "Validate regression test at affected SHA"
            if validate_at_affected
            else "Run regression test at IC SHA"
        )
        task = await TaskService().create_task(
            session,
            cycle_id,
            title,
            WorkType.VERIFICATION,
            TaskOrigin.CONTROL_PLANE,
            ctx,
        )
        body = TaskContractBody(
            objective=title,
            work_type=WorkType.VERIFICATION,
            inputs=[VersionedRef(ref_type="DEFECT", ref_id=defect.id)],
            repository_id=cycle.repository_id,
            executor_kind="DETERMINISTIC",
            deterministic_executor="reproduction.regression",
            required_outputs=[],
        )
        contract = TaskContract(
            task_id=task.id,
            key="v1",
            version=1,
            status=TaskContractStatus.ISSUED,
            body={
                **body.model_dump(mode="json"),
                "defect_id": str(defect.id),
                "regression_test_path": regression_test_path,
                "commit_sha": commit_sha,
                "integration_candidate_id": str(integration_candidate_id),
                "phase": "REGRESSION_VALIDATION" if validate_at_affected else "REGRESSION",
                "regression_test_validated": validate_at_affected,
            },
            content_hash=sha256_hex(
                f"regression-{'val' if validate_at_affected else 'run'}-{cycle_id}"
            ),
            compiled_by="bug_fix",
        )
        session.add(contract)
        await session.flush()
        task.current_contract_id = contract.id
        await TaskService().mark_ready(session, task.id, ctx)
        return {"regression_task_id": str(task.id)}

    async def _regression_test_path_for_cycle(
        self, session: AsyncSession, cycle_id: uuid.UUID
    ) -> str | None:
        from core.domain.enums import SpecStatus
        from core.planning.implementation_specs.service import ImplementationSpecService
        from core.planning.models import ImplementationSpec
        from core.product_model.defects.repair import RepairSpecValidator

        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None:
            return None
        impl = (
            await session.execute(
                select(ImplementationSpec)
                .where(
                    ImplementationSpec.project_id == cycle.project_id,
                    ImplementationSpec.kind == "REPAIR",
                    ImplementationSpec.status == SpecStatus.APPROVED,
                )
                .order_by(ImplementationSpec.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        defect = await DefectService().get_by_cycle(session, cycle_id)
        triage_path: str | None = None
        if defect and isinstance(defect.triage, dict):
            raw = defect.triage.get("regression_test_path")
            if isinstance(raw, str) and raw.startswith("tests/") and "*" not in raw:
                triage_path = raw
        if impl is None:
            return triage_path
        from_body = RepairSpecValidator().regression_test_path_from_body(
            ImplementationSpecService().parse_body(impl)
        )
        if from_body is not None and not from_body.endswith(".py"):
            from_body = None
        # Prefer explicit triage path (deterministic repair / intake) over LLM spec heuristics.
        return triage_path or from_body

    async def run_regression_stage(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> None:
        from sqlalchemy import select

        from core.integration.enums import ICStatus
        from core.integration.models import IntegrationCandidate

        defect = await DefectService().get_by_cycle(session, cycle_id)
        cycle = await session.get(DeliveryCycle, cycle_id)
        if defect is None or cycle is None:
            return
        ic = (
            await session.execute(
                select(IntegrationCandidate).where(
                    IntegrationCandidate.delivery_cycle_id == cycle_id,
                    IntegrationCandidate.status == ICStatus.READY,
                )
            )
        ).scalar_one_or_none()
        if ic is None or ic.integrated_sha is None:
            return
        from core.product_model.defects.models import Reproduction

        pre = (
            await session.execute(
                select(Reproduction)
                .where(
                    Reproduction.defect_id == defect.id,
                    Reproduction.phase == "PRE_REPAIR",
                )
                .order_by(Reproduction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if pre is None:
            return
        await self.schedule_reproduction_run_post(
            session, cycle_id, pre.artifact_id, ic.integrated_sha, ctx
        )
        test_path = await self._regression_test_path_for_cycle(session, cycle_id)
        if test_path:
            await self.schedule_regression_test_run(
                session,
                cycle_id,
                test_path,
                ic.integrated_sha,
                ctx,
                integration_candidate_id=ic.id,
            )
