from __future__ import annotations

import uuid
from dataclasses import dataclass

from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.approvals.models import Approval
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import (
    ActorKind,
    ApprovalStatus,
    ApprovalType,
    DeliveryCycleType,
    TaskContractStatus,
    TaskOrigin,
    TaskStatus,
    WorkType,
)
from core.domain.projects.models import Project
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody, VersionedRef
from core.domain.tasks.models import Task
from core.domain.tasks.service import TaskService
from core.execution.artifacts import ArtifactStore
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ReadyTaskBundle:
    actor: Actor
    project: Project
    cycle: DeliveryCycle
    task: Task
    contract: TaskContract
    ctx: CommandContext


async def seed_ready_task(
    session: AsyncSession,
    *,
    key_prefix: str = "ex",
    body: TaskContractBody | None = None,
    actor: Actor | None = None,
    with_pending_required_approval: bool = False,
) -> ReadyTaskBundle:
    if actor is None:
        actor = Actor(kind=ActorKind.SYSTEM, name=f"{key_prefix}-actor", roles=["SYSTEM"])
        session.add(actor)
    project = Project(key=f"{key_prefix}-proj", name=f"Project {key_prefix}")
    session.add(project)
    await session.flush()
    ctx = CommandContext(actor=actor, correlation_id=f"{key_prefix}-corr")
    cycle = DeliveryCycle(
        project_id=project.id,
        key=f"C-{key_prefix}",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="execution test",
        state="DEVELOPMENT",
        state_version=0,
        opened_by_actor_id=actor.id,
    )
    session.add(cycle)
    await session.flush()
    task = await TaskService().create_task(
        session,
        cycle.id,
        f"Task {key_prefix}",
        WorkType.ANALYSIS,
        TaskOrigin.CONTROL_PLANE,
        ctx,
    )
    pending_approval: Approval | None = None
    if with_pending_required_approval:
        pending_approval = Approval(
            key=f"A-{key_prefix}",
            project_id=project.id,
            approval_type=ApprovalType.ACTION,
            subject_type="task",
            subject_id=task.id,
            subject_version=1,
            subject_hash=f"hash-{key_prefix}",
            status=ApprovalStatus.PENDING,
            requested_by_actor_id=actor.id,
        )
        session.add(pending_approval)
        await session.flush()
    contract_body = body or TaskContractBody(
        objective="test",
        work_type=WorkType.ANALYSIS,
        inputs=[],
        executor_kind="DETERMINISTIC",
        deterministic_executor="noop.verify_artifact",
    )
    if pending_approval is not None:
        contract_body = contract_body.model_copy(
            update={"required_approvals": [pending_approval.id]}
        )
    contract = TaskContract(
        task_id=task.id,
        key="v1",
        version=1,
        status=TaskContractStatus.ISSUED,
        body=contract_body.model_dump(mode="json"),
        content_hash=f"hash-{key_prefix}",
        compiled_by="test",
    )
    session.add(contract)
    await session.flush()
    task.current_contract_id = contract.id
    task.status = TaskStatus.READY
    await session.flush()
    return ReadyTaskBundle(
        actor=actor,
        project=project,
        cycle=cycle,
        task=task,
        contract=contract,
        ctx=ctx,
    )


async def seed_input_artifact(
    session: AsyncSession,
    bundle: ReadyTaskBundle,
    *,
    text: str,
    kind: str = "DIAGNOSTIC_INPUT",
) -> uuid.UUID:
    store = ArtifactStore()
    row = await store.put(
        session,
        project_id=bundle.project.id,
        delivery_cycle_id=bundle.cycle.id,
        execution_id=None,
        kind=kind,
        schema_name="Text",
        schema_version="1",
        content={"text": text},
    )
    return row.id


def contract_with_inputs(
    base: TaskContractBody,
    artifact_id: uuid.UUID,
    *,
    agent_profile: str | None = None,
    required_outputs: list[str] | None = None,
) -> TaskContractBody:
    return base.model_copy(
        update={
            "inputs": [VersionedRef(ref_type="ARTIFACT", ref_id=artifact_id, key="input")],
            "executor_kind": "AGENT_RUNTIME",
            "agent_profile": agent_profile or "diagnostic.structured_echo",
            "deterministic_executor": None,
            "required_outputs": required_outputs or ["artifact:DIAGNOSTIC_SUMMARY"],
        }
    )
