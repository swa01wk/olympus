from __future__ import annotations

import re
import uuid

from agents.atlas.schemas import ArchitectureProposal
from agents.kira.schemas import ImplementationSpecDraft, TaskPlan
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.executions.models import Execution, ExecutionSnapshot
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.planning.architecture.service import ArchitectureService
from core.planning.implementation_specs.service import ImplementationSpecService
from core.planning.schemas import ArchitectureBody, ComponentDef
from core.planning.task_plans.service import TaskPlanService


def _normalize_impl_spec_file_scope(patterns: list[str]) -> list[str]:
    out: list[str] = []
    for raw in patterns:
        g = raw.strip().replace("\\", "/")
        if g.endswith("/*") and not g.endswith("/**"):
            g = g[:-2] + "/**"
        out.append(g)
    return out


def _component_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _resolve_component(name: str, components: list[ComponentDef]) -> str:
    """Map a code reference (``app.services.ticket_service.TicketService``) to a component name.

    Matches the class or module name to a component name, then the module's package to a unique
    component directory. Unresolvable names are returned unchanged so conformance still flags them.
    """
    if any(c.name == name for c in components):
        return name
    by_token = {_component_token(c.name): c.name for c in components}
    parts = [p for p in re.split(r"[./\\]", name.strip().removesuffix(".py")) if p]
    module = [p for p in parts if not p[0].isupper()]
    for candidate in [name, *reversed(parts)]:
        if (hit := by_token.get(_component_token(candidate))) is not None:
            return hit
    if len(module) < 2:
        return name
    package = "/".join(module[:-1])
    in_package = [c.name for c in components if c.directory.strip("/") == package]
    return in_package[0] if len(in_package) == 1 else name


async def _sanitize_implementation_spec_draft(
    session: AsyncSession,
    project_id: uuid.UUID,
    draft: ImplementationSpecDraft,
) -> ImplementationSpecDraft:
    arch_svc = ArchitectureService()
    effective = await arch_svc.effective(session, project_id)
    if effective is None:
        return draft
    _arch, body_arch, contracts = effective
    comp_names = {c.name for c in body_arch.components}
    contract_keys = {c.key for c in contracts}
    decision_ids = {d.id for d in body_arch.decisions}
    known_refs = comp_names | contract_keys | decision_ids

    body = draft.body
    apis = [api for api in body.apis if not api.contract_key or api.contract_key in contract_keys]
    components = list(
        dict.fromkeys(_resolve_component(c, body_arch.components) for c in body.components)
    )
    return draft.model_copy(
        update={
            "body": body.model_copy(
                update={
                    "components": components,
                    "file_scope": _normalize_impl_spec_file_scope(body.file_scope),
                    "architecture_refs": [r for r in body.architecture_refs if r in known_refs],
                    "apis": apis,
                }
            )
        }
    )


def _sanitize_architecture_proposal(proposal: ArchitectureProposal) -> ArchitectureProposal:
    body = proposal.body
    layer_set = set(body.layers)
    clean_rules: list[str] = []
    for rule in body.dependency_rules:
        parts = [p.strip() for p in rule.replace("→", "->").split("->")]
        if len(parts) == 2 and parts[0] in layer_set and parts[1] in layer_set:
            clean_rules.append(f"{parts[0]} -> {parts[1]}")
    seen_dirs: set[str] = set()
    components = []
    for comp in body.components:
        directory = comp.directory
        if directory in seen_dirs:
            directory = f"{directory.rstrip('/')}/{comp.name}"
        seen_dirs.add(directory)
        if directory != comp.directory:
            comp = comp.model_copy(update={"directory": directory})
        components.append(comp)
    new_body = ArchitectureBody(
        summary=body.summary,
        technology_stack=body.technology_stack,
        components=components,
        layers=body.layers,
        dependency_rules=clean_rules,
        directory_conventions=body.directory_conventions,
        decisions=body.decisions,
        constraints=body.constraints,
        risks=body.risks,
    )
    open_questions = [q.model_copy(update={"blocking": False}) for q in proposal.open_questions]
    return proposal.model_copy(update={"body": new_body, "open_questions": open_questions})


async def _implementation_spec_mode_for_execution(
    session: AsyncSession,
    execution: Execution,
) -> str:
    if execution.snapshot_id is not None:
        snap = await session.get(ExecutionSnapshot, execution.snapshot_id)
        if snap is not None and isinstance(snap.content, dict):
            mode = str(snap.content.get("implementation_spec_mode", "")).strip()
            if mode:
                return mode
    contract = await session.get(TaskContract, execution.task_contract_id)
    if contract is not None and isinstance(contract.body, dict):
        embedded = contract.body.get("_snapshot")
        if isinstance(embedded, dict):
            return str(embedded.get("implementation_spec_mode", "")).strip()
    return ""


class PlanningCompletionService:
    async def persist_from_execution(
        self,
        session: AsyncSession,
        execution: Execution,
        contract_profile: str,
        output: dict[str, object],
        ctx: CommandContext,
    ) -> None:
        task = await session.get(Task, execution.task_id)
        if task is None:
            return
        if contract_profile == "atlas.propose_architecture":
            from core.domain.delivery_cycles.models import DeliveryCycle

            cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
            if cycle is None:
                return
            proposal = _sanitize_architecture_proposal(ArchitectureProposal.model_validate(output))
            arch_row = await ArchitectureService().persist_proposal(
                session,
                project_id=cycle.project_id,
                proposal=proposal,
                execution_id=execution.id,
                ctx=ctx,
                delivery_cycle_id=cycle.id,
            )
            from core.review.completion import complete_revision_if_needed

            await complete_revision_if_needed(session, execution, arch_row.id, ctx)
        elif contract_profile == "kira.implementation_spec" and task.governing_ref_id:
            from core.domain.delivery_cycles.models import DeliveryCycle
            from core.domain.enums import DeliveryCycleType, SpecStatus
            from core.planning.implementation_specs.delta import ImplementationSpecDeltaService
            from core.product_model.models import FeatureSpec

            spec = await session.get(FeatureSpec, task.governing_ref_id)
            draft = ImplementationSpecDraft.model_validate(output)
            cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
            if spec is not None:
                draft = await _sanitize_implementation_spec_draft(session, spec.project_id, draft)
            impl_mode = await _implementation_spec_mode_for_execution(session, execution)
            if impl_mode == "REPAIR" and spec is not None:
                draft = await _sanitize_implementation_spec_draft(session, spec.project_id, draft)
                repair_row = await ImplementationSpecService().persist_repair_draft(
                    session,
                    feature_spec_id=task.governing_ref_id,
                    draft=draft,
                    execution_id=execution.id,
                    ctx=ctx,
                    delivery_cycle_id=cycle.id if cycle is not None else None,
                )
                from core.review.completion import complete_revision_if_needed

                await complete_revision_if_needed(session, execution, repair_row.id, ctx)
                return
            is_delta = impl_mode == "DELTA" or (
                impl_mode != "FULL"
                and cycle is not None
                and cycle.type == DeliveryCycleType.FEATURE_CHANGE
            )
            if is_delta and cycle is not None and spec is not None:
                from core.planning.implementation_specs.delta import (
                    resolve_parent_implementation_spec,
                )

                parent = await resolve_parent_implementation_spec(
                    session,
                    project_id=spec.project_id,
                    feature_spec_id=spec.id,
                )
                if parent is not None:
                    delta_svc = ImplementationSpecDeltaService()
                    ok, errors = await delta_svc.validate_for_cycle(
                        session, delivery_cycle_id=cycle.id, body=draft.body
                    )
                    if not ok:
                        from core.domain.exceptions import DomainError

                        raise DomainError(
                            code="IMPACT_INCONSISTENT",
                            message="ImplementationSpec delta failed impact consistency",
                            details={"errors": errors},
                        )
                    row = await delta_svc.persist_delta(
                        session,
                        parent_impl_id=parent.id,
                        body=draft.body,
                        feature_spec_id=spec.id,
                        execution_id=execution.id,
                        ctx=ctx,
                    )
                    row.status = SpecStatus.PROPOSED
                    await session.flush()
                    from core.review.completion import complete_revision_if_needed

                    await complete_revision_if_needed(session, execution, row.id, ctx)
                    return
            impl_row = await ImplementationSpecService().persist_draft(
                session,
                feature_spec_id=task.governing_ref_id,
                draft=draft,
                execution_id=execution.id,
                ctx=ctx,
                delivery_cycle_id=cycle.id if cycle is not None else None,
            )
            from core.review.completion import complete_revision_if_needed

            await complete_revision_if_needed(session, execution, impl_row.id, ctx)
        elif contract_profile == "kira.task_plan":
            from core.domain.delivery_cycles.models import DeliveryCycle

            plan = TaskPlan.model_validate(output)
            raw_ids = output.get("_implementation_spec_ids")
            impl_ids: list[uuid.UUID] = []
            if isinstance(raw_ids, list):
                impl_ids = [uuid.UUID(str(i)) for i in raw_ids]
            if not impl_ids:
                cycle = await session.get(DeliveryCycle, execution.delivery_cycle_id)
                if cycle is not None:
                    impl_ids = [
                        r.id
                        for r in await TaskPlanService().implementation_specs_for_cycle(
                            session, cycle
                        )
                    ]
            await TaskPlanService().persist_proposed(
                session,
                delivery_cycle_id=execution.delivery_cycle_id,
                plan=plan,
                implementation_spec_ids=impl_ids,
                execution_id=execution.id,
                ctx=ctx,
            )
