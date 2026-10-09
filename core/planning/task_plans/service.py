from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.approvals.service import ApprovalService
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import ApprovalType, DeliveryCycleType, SpecStatus, TaskOrigin, WorkType
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError
from core.domain.task_contracts.service import ContractService
from core.domain.tasks.models import Task
from core.domain.tasks.service import TaskService
from core.planning.compiler import CompilerInputs, TaskContractCompiler
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.models import Architecture, ImplementationSpec, TaskPlanRow, TaskSpecRef
from core.planning.schemas import ImplementationSpecBody, PlanValidationReport, TaskPlan
from core.planning.task_plans.validation import TaskPlanValidator
from core.policy.policy_service import PolicyService, ensure_policy_version
from core.product_model.models import AcceptanceCriterion, FeatureSpec, ScopeSet, ScopeSetItem
from core.review.auto_request import ensure_pending_approval


@dataclass(frozen=True, slots=True)
class TaskPlanCheck:
    plan: TaskPlan
    report: PlanValidationReport
    implementation_spec_ids: list[uuid.UUID]
    impl_by_lineage: dict[str, ImplementationSpec]
    ac_by_key: dict[str, AcceptanceCriterion]
    policy: PolicyService


class TaskPlanService:
    def __init__(self) -> None:
        self._validator = TaskPlanValidator()
        self._impl = ImplementationSpecService()
        self._compiler = TaskContractCompiler()

    async def _compiler_impact_fields(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
    ) -> tuple[frozenset[str] | None, tuple[str, ...], tuple[str, ...]]:
        if cycle.type not in {
            DeliveryCycleType.FEATURE_CHANGE,
            DeliveryCycleType.BUG_FIX,
        }:
            return None, (), ()
        from core.intelligence.impact.engine import ImpactEngine
        from core.intelligence.impact.enums import ImpactItemType
        from core.intelligence.impact.models import ImpactItem

        ia = await ImpactEngine().latest_complete(session, cycle.id)
        if ia is None:
            return None, (), ()
        items = list(
            (
                await session.execute(
                    select(ImpactItem).where(
                        ImpactItem.impact_assessment_id == ia.id,
                        ImpactItem.selected_for_verification.is_(True),
                    )
                )
            ).scalars()
        )
        paths: set[str] = set()
        baselines: list[str] = []
        tests: list[str] = []
        for item in items:
            if item.path:
                if isinstance(item.path, list):
                    paths.update(str(p) for p in item.path)
                else:
                    paths.add(str(item.path))
            if item.item_type == ImpactItemType.BASELINE.value:
                baselines.append(item.ref)
            if item.item_type == ImpactItemType.TEST.value:
                tests.append(item.ref)
        return frozenset(paths), tuple(sorted(set(baselines))), tuple(sorted(set(tests)))

    async def _approved_repair_impl_for_cycle(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
    ) -> ImplementationSpec | None:
        return (
            await session.execute(
                select(ImplementationSpec)
                .where(
                    ImplementationSpec.project_id == cycle.project_id,
                    ImplementationSpec.kind == "REPAIR",
                    ImplementationSpec.status == SpecStatus.APPROVED,
                )
                .order_by(ImplementationSpec.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def implementation_specs_for_cycle(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
    ) -> list[ImplementationSpec]:
        """Approved implementation specs a cycle's task plan is planned and validated against.

        One row per lineage (its latest APPROVED version): the cycle's REPAIR spec for a bug fix,
        otherwise the specs of the features in the cycle's scope, otherwise every lineage in the
        project.
        """
        if cycle.type == DeliveryCycleType.BUG_FIX:
            repair = await self._approved_repair_impl_for_cycle(session, cycle)
            if repair is not None:
                return [repair]
        query = (
            select(ImplementationSpec)
            .where(
                ImplementationSpec.project_id == cycle.project_id,
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
            .order_by(ImplementationSpec.version.desc())
        )
        scope_set = (
            await session.execute(
                select(ScopeSet)
                .where(ScopeSet.delivery_cycle_id == cycle.id)
                .order_by(ScopeSet.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if scope_set is not None:
            feature_lineages = (
                select(FeatureSpec.lineage_key)
                .join(ScopeSetItem, ScopeSetItem.feature_spec_id == FeatureSpec.id)
                .where(ScopeSetItem.scope_set_id == scope_set.id)
            )
            scoped = query.join(
                FeatureSpec, FeatureSpec.id == ImplementationSpec.feature_spec_id
            ).where(FeatureSpec.lineage_key.in_(feature_lineages))
            rows = list((await session.execute(scoped)).scalars())
        else:
            rows = []
        if not rows:
            rows = list((await session.execute(query)).scalars())
        latest: dict[str, ImplementationSpec] = {}
        for row in rows:
            latest.setdefault(row.lineage_key, row)
        return list(latest.values())

    def _enrich_bug_fix_task_plan(
        self,
        plan: TaskPlan,
        repair_impl: ImplementationSpec,
    ) -> TaskPlan:
        from core.product_model.defects.repair import RepairSpecValidator

        body = self._impl.parse_body(repair_impl)
        reg_path = RepairSpecValidator().regression_test_path_from_body(body)
        if not reg_path:
            reg_path = "tests/test_closed_ticket_update.py"
        lineage = repair_impl.lineage_key
        new_tasks = []
        for task in plan.tasks:
            outs = list(task.required_outputs)
            if not any("tests/" in o and "olympus_repro" not in o for o in outs):
                outs.append(f"file:{reg_path}")
            allowed = list(task.allowed_scope) or list(body.file_scope)
            new_tasks.append(
                task.model_copy(
                    update={
                        "implementation_spec_ref": lineage,
                        "required_outputs": outs,
                        "allowed_scope": allowed,
                    }
                )
            )
        return plan.model_copy(update={"tasks": new_tasks})

    async def persist_proposed(
        self,
        session: AsyncSession,
        *,
        delivery_cycle_id: uuid.UUID,
        plan: TaskPlan,
        implementation_spec_ids: list[uuid.UUID],
        execution_id: uuid.UUID | None,
        ctx: CommandContext,
    ) -> TaskPlanRow:
        cycle = await session.get(DeliveryCycle, delivery_cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
        check = await self.check_plan(session, cycle, plan, implementation_spec_ids)
        if not check.report.ok:
            raise DomainError(
                code="VALIDATION_FAILED",
                message="TaskPlan validation failed",
                details={"errors": check.report.errors},
            )
        plan = check.plan

        prior = await session.execute(
            select(TaskPlanRow)
            .where(
                TaskPlanRow.delivery_cycle_id == delivery_cycle_id,
                TaskPlanRow.status.in_(("PROPOSED", "ACCEPTED")),
            )
            .order_by(TaskPlanRow.created_at.desc())
        )
        for old in prior.scalars():
            old.status = "SUPERSEDED"

        row = TaskPlanRow(
            delivery_cycle_id=delivery_cycle_id,
            execution_id=execution_id,
            status="PROPOSED",
            implementation_spec_ids=[str(i) for i in check.implementation_spec_ids],
            body=plan.model_dump(mode="json"),
            validation_report=check.report.model_dump(mode="json"),
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="task_plan",
            aggregate_id=row.id,
            event_type="task_plan.proposed",
            payload={"task_count": len(plan.tasks)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        await ensure_pending_approval(
            session,
            project_id=cycle.project_id,
            approval_type=ApprovalType.TASK_PLAN,
            subject_type="task_plan",
            subject_id=row.id,
            subject_version=1,
            subject_hash=sha256_hex(row.body),
            delivery_cycle_id=delivery_cycle_id,
            ctx=ctx,
        )
        return row

    async def check_plan(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        plan: TaskPlan,
        implementation_spec_ids: list[uuid.UUID],
    ) -> TaskPlanCheck:
        """Validate a plan exactly as accept does; bug-fix plans come back enriched.

        Enrichment is idempotent, so a stored plan re-checked at accept keeps its approved hash.
        """
        impl_ids = list(implementation_spec_ids) or [
            r.id for r in await self.implementation_specs_for_cycle(session, cycle)
        ]
        impl_by_lineage: dict[str, ImplementationSpec] = {}
        specs_by_lineage: dict[str, ImplementationSpecBody] = {}
        for impl_id in impl_ids:
            impl = await session.get(ImplementationSpec, impl_id)
            if impl is None or impl.status != SpecStatus.APPROVED:
                raise DomainError(code="INVALID_STATE", message="ImplementationSpec not approved")
            impl_by_lineage[impl.lineage_key] = impl
            specs_by_lineage[impl.lineage_key] = self._impl.parse_body(impl)

        errors: list[str] = []
        if cycle.type == DeliveryCycleType.BUG_FIX:
            from core.product_model.defects.repair import RepairSpecValidator

            repair_impl = await self._approved_repair_impl_for_cycle(session, cycle)
            if repair_impl is not None:
                plan = self._enrich_bug_fix_task_plan(plan, repair_impl)
            ok, repair_errors = RepairSpecValidator().validate_task_plan(plan)
            if not ok:
                errors.extend(repair_errors)

        scope_set = (
            await session.execute(
                select(ScopeSet)
                .where(ScopeSet.delivery_cycle_id == cycle.id)
                .order_by(ScopeSet.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        feature_spec_ids: list[uuid.UUID] = []
        if scope_set:
            items = await session.execute(
                select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set.id)
            )
            feature_spec_ids = [i.feature_spec_id for i in items.scalars()]

        mandatory_ac: set[str] = set()
        ac_by_key: dict[str, AcceptanceCriterion] = {}
        for fs_id in feature_spec_ids:
            acs = await session.execute(
                select(AcceptanceCriterion).where(AcceptanceCriterion.feature_spec_id == fs_id)
            )
            for ac in acs.scalars():
                ac_by_key[ac.lineage_key] = ac
                if ac.mandatory:
                    mandatory_ac.add(ac.lineage_key)

        policy = await ensure_policy_version(session)
        report = self._validator.validate(
            plan,
            specs_by_lineage,
            mandatory_ac,
            max_tasks=int(policy.get("planning.max_tasks_per_plan", 12)),
        )
        errors.extend(report.errors)
        return TaskPlanCheck(
            plan=plan,
            report=PlanValidationReport(ok=not errors, errors=errors),
            implementation_spec_ids=impl_ids,
            impl_by_lineage=impl_by_lineage,
            ac_by_key=ac_by_key,
            policy=policy,
        )

    async def accept(
        self,
        session: AsyncSession,
        task_plan_id: uuid.UUID,
        ctx: CommandContext,
    ) -> TaskPlanRow:
        from core.domain.delivery_cycles.models import DeliveryCycle

        plan_row = await session.get(TaskPlanRow, task_plan_id)
        if plan_row is None:
            raise DomainError(code="NOT_FOUND", message="TaskPlan not found")
        if plan_row.status != "PROPOSED":
            raise DomainError(code="INVALID_STATE", message="TaskPlan must be PROPOSED")

        subject_hash = sha256_hex(plan_row.body or {})
        approved = await ApprovalService().is_satisfied(
            session,
            ApprovalType.TASK_PLAN,
            "task_plan",
            plan_row.id,
            subject_hash,
        )
        if not approved:
            raise DomainError(
                code="APPROVAL_REQUIRED",
                message="TASK_PLAN approval required before accept",
            )

        cycle = await session.get(DeliveryCycle, plan_row.delivery_cycle_id)
        if cycle is None:
            raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")

        check = await self.check_plan(
            session,
            cycle,
            TaskPlan.model_validate(plan_row.body),
            [uuid.UUID(i) for i in plan_row.implementation_spec_ids],
        )
        plan_row.validation_report = check.report.model_dump(mode="json")
        if not check.report.ok:
            raise DomainError(
                code="VALIDATION_FAILED",
                message="TaskPlan validation failed",
                details={"errors": check.report.errors},
            )
        plan = check.plan
        impl_by_lineage = check.impl_by_lineage
        ac_by_key = check.ac_by_key
        policy = check.policy

        task_origin = (
            TaskOrigin.REPAIR
            if cycle.type == DeliveryCycleType.BUG_FIX
            else TaskOrigin.IMPLEMENTATION_PLAN
        )
        task_svc = TaskService()
        ref_to_task: dict[str, Task] = {}
        for draft in plan.tasks:
            impl = impl_by_lineage[draft.implementation_spec_ref]
            task = await task_svc.create_task(
                session,
                cycle.id,
                draft.title,
                WorkType.CODE_CHANGE,
                task_origin,
                ctx,
            )
            task.implementation_spec_id = impl.id
            ref_to_task[draft.ref] = task
            fs = await session.get(FeatureSpec, impl.feature_spec_id)
            session.add(
                TaskSpecRef(
                    task_id=task.id,
                    ref_type="IMPLEMENTATION_SPEC",
                    ref_id=impl.id,
                    ref_version=impl.version,
                )
            )
            if fs:
                session.add(
                    TaskSpecRef(
                        task_id=task.id,
                        ref_type="FEATURE_SPEC",
                        ref_id=fs.id,
                        ref_version=fs.version,
                    )
                )
            for ac_key in draft.ac_refs:
                ac_row = ac_by_key.get(ac_key)
                if ac_row is not None:
                    session.add(
                        TaskSpecRef(
                            task_id=task.id,
                            ref_type="ACCEPTANCE_CRITERION",
                            ref_id=ac_row.id,
                            ref_version=1,
                        )
                    )

        for dep in plan.dependencies:
            t = ref_to_task[dep.task_ref]
            d = ref_to_task[dep.depends_on_ref]
            await task_svc.add_dependency(session, t.id, d.id)

        arch_id = next(iter(impl_by_lineage.values())).architecture_id
        from core.planning.architecture.service import ArchitectureService

        arch_row = await session.get(Architecture, arch_id)
        arch_svc = ArchitectureService()
        arch_body = arch_svc.parse_body(arch_row) if arch_row else None

        impact_paths, baseline_keys, test_refs = await self._compiler_impact_fields(session, cycle)
        extra_constraints: tuple[str, ...] = ()
        deny_prefixes: tuple[str, ...] = ()
        if cycle.type == DeliveryCycleType.BUG_FIX:
            from core.product_model.defects.models import Reproduction
            from core.product_model.defects.service import DefectService

            defect = await DefectService().get_by_cycle(session, cycle.id)
            deny_prefixes = ("tests/olympus_repro",)
            if defect is not None:
                pre = (
                    await session.execute(
                        select(Reproduction).where(
                            Reproduction.defect_id == defect.id,
                            Reproduction.phase == "PRE_REPAIR",
                        )
                    )
                ).scalar_one_or_none()
                if pre is not None:
                    extra_constraints = (
                        f"make the reproduction pass: artifact:{pre.artifact_id}",
                        "add a regression test equivalent to the reproduction in tests/",
                        "preserve impacted baselines",
                    )

        contract_svc = ContractService()
        for draft in plan.tasks:
            task = ref_to_task[draft.ref]
            impl = impl_by_lineage[draft.implementation_spec_ref]
            fs = await session.get(FeatureSpec, impl.feature_spec_id)
            assert fs is not None and arch_row is not None and arch_body is not None
            ac_triples: list[tuple[uuid.UUID, int, str]] = []
            for ac_key in draft.ac_refs:
                ac_row = ac_by_key.get(ac_key)
                if ac_row is not None:
                    ac_triples.append((ac_row.id, 1, ac_row.lineage_key))
            has_deps = any(d.task_ref == draft.ref for d in plan.dependencies)
            body, inputs_hash = self._compiler.compile(
                CompilerInputs(
                    task_draft=draft,
                    implementation_spec_id=impl.id,
                    implementation_spec_version=impl.version,
                    implementation_spec_lineage=impl.lineage_key,
                    implementation_spec_body=self._impl.parse_body(impl),
                    feature_spec_id=fs.id,
                    feature_spec_version=fs.version,
                    feature_spec_lineage=fs.lineage_key,
                    feature_spec_rules=list(fs.body.get("rules") or []),
                    architecture_id=arch_row.id,
                    architecture_version=arch_row.version,
                    architecture_body=arch_body,
                    ac_refs=ac_triples,
                    repository_id=cycle.repository_id,
                    has_dependencies=has_deps,
                    policy=policy,
                    impact_file_paths=impact_paths,
                    impacted_baseline_keys=baseline_keys,
                    new_acceptance_test_refs=test_refs,
                    extra_constraints=extra_constraints,
                    deny_scope_prefixes=deny_prefixes,
                )
            )
            contract = await contract_svc.create_draft(
                session,
                task.id,
                body,
                "compiler:task_plan_v1",
                ctx,
                inputs_hash=inputs_hash,
            )
            await contract_svc.issue(session, contract.id, ctx)
            await task_svc.mark_ready(session, task.id, ctx)

        plan_row.status = "ACCEPTED"
        await append_domain_event(
            session,
            aggregate_type="task_plan",
            aggregate_id=plan_row.id,
            event_type="task_plan.accepted",
            payload={"task_count": len(plan.tasks)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            delivery_cycle_id=cycle.id,
        )
        return plan_row
