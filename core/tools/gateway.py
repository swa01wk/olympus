"""ToolGateway — validation pipeline and action persistence."""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.actions.models import ActionRequest, ActionResult
from core.domain.actors.models import Actor
from core.domain.enums import ActionStatus, ActorKind
from core.domain.events.append import append_domain_event
from core.domain.execution_workspaces.models import ExecutionWorkspace
from core.domain.executions.models import Execution, ExecutionSnapshot
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import TaskContractBody
from core.policy.action_policy import evaluate_action_policy
from core.repositories.workspace_locator import WorkspaceLocator
from core.tools.catalog import get_tool
from core.tools.context import ToolExecutionContext
from core.tools.handlers import get_handler
from core.tools.paths import PathPolicyViolation
from core.tools.schemas import GatewayToolResult
from core.tools.tokens import TokenValidationError, validate_token

_SECRET_PARAM = re.compile(r"(credential|token|password)", re.I)


def redact_params(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in params.items():
        if _SECRET_PARAM.search(key):
            out[key] = "[REDACTED]"
        else:
            out[key] = value
    return out


def _params_hash(params: dict[str, Any]) -> str:
    payload = json.dumps(redact_params(params), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


async def _default_actor_id(session: AsyncSession, kind: ActorKind = ActorKind.SYSTEM) -> uuid.UUID:
    result = await session.execute(select(Actor).where(Actor.kind == kind).limit(1))
    actor = result.scalar_one_or_none()
    if actor is None:
        raise ValueError(f"No {kind.value} actor configured")
    return actor.id


class ToolGateway:
    def __init__(self, session: AsyncSession, locator: WorkspaceLocator | None = None) -> None:
        self._session = session
        self._locator = locator or WorkspaceLocator()

    async def handle(
        self,
        token: str,
        tool: str,
        params: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> GatewayToolResult:
        start = time.monotonic()
        from core.observability.instrumentation import tool_span

        with tool_span(tool=tool):
            return await self._handle_inner(token, tool, params, idempotency_key, start)

    async def _handle_inner(
        self,
        token: str,
        tool: str,
        params: dict[str, Any],
        idempotency_key: str | None,
        start: float,
    ) -> GatewayToolResult:
        denial: list[str] = []
        try:
            execution, lease = await validate_token(self._session, token)
        except TokenValidationError as exc:
            actor_id = await _default_actor_id(self._session)
            req = await self._persist_denied(
                tool=tool,
                params=params,
                reasons=[exc.reason],
                execution_id=None,
                actor_id=actor_id,
                correlation_id="invalid-token",
            )
            from core.observability.metrics import TOOLGATEWAY_DENIALS

            TOOLGATEWAY_DENIALS.labels(reason=exc.reason).inc()
            return GatewayToolResult(
                action_request_id=req.id,
                status="DENIED",
                denial_reasons=[exc.reason],
            )

        from core.observability.context import bind

        bind(olympus_execution_id=str(execution.id))

        contract_row = await self._session.get(TaskContract, execution.task_contract_id)
        contract = TaskContractBody.model_validate(contract_row.body) if contract_row else None
        if contract is not None and not contract.allowed_scope:
            contract = contract.model_copy(update={"allowed_scope": ["**"]})
        agent_profile = execution.agent_profile
        denial = await self._validate(
            execution=execution,
            contract=contract,
            agent_profile=agent_profile,
            tool=tool,
            params=params,
            actor_kind=ActorKind.AGENT,
        )
        if denial:
            actor_id = await _default_actor_id(self._session, ActorKind.AGENT)
            req = await self._persist_denied(
                tool=tool,
                params=params,
                reasons=denial,
                execution_id=execution.id,
                lease_id=lease.id,
                actor_id=actor_id,
                correlation_id=str(execution.id),
                contract=contract_row,
                agent_profile=agent_profile,
            )
            return GatewayToolResult(
                action_request_id=req.id,
                status="DENIED",
                denial_reasons=denial,
            )

        snapshot = await self._session.get(ExecutionSnapshot, execution.snapshot_id)
        policy_version_id = str(snapshot.policy_version_id) if snapshot else None
        tool_def = get_tool(tool)
        decision = evaluate_action_policy(
            resource=tool_def.resource,
            action=tool_def.action,
            tool=tool,
            agent_profile=agent_profile,
            actor_kind=ActorKind.AGENT,
            params=params,
            policy_version_id=policy_version_id,
            risk_tier=snapshot.risk_tier if snapshot else None,
        )
        actor_id = await _default_actor_id(self._session, ActorKind.AGENT)
        req = ActionRequest(
            key=f"AR-{uuid.uuid4().hex[:12]}",
            execution_id=execution.id,
            lease_id=lease.id,
            actor_id=actor_id,
            agent_profile=agent_profile,
            tool=tool,
            resource=tool_def.resource,
            action=tool_def.action,
            params=redact_params(params),
            params_hash=_params_hash(params),
            task_contract_id=execution.task_contract_id,
            task_contract_version=contract_row.version if contract_row else None,
            idempotency_key=idempotency_key,
            correlation_id=str(execution.id),
            status=ActionStatus.REQUESTED,
            policy_decision={
                "decision": decision.decision,
                "rule_ids": decision.rule_ids,
                "reasons": decision.reasons,
                "policy_version_id": decision.policy_version_id,
            },
        )
        self._session.add(req)
        await self._session.flush()

        if decision.decision == "DENY":
            req.status = ActionStatus.DENIED
            duration_ms = int((time.monotonic() - start) * 1000)
            await self._write_result(req, "DENIED", None, denial, duration_ms)
            return GatewayToolResult(
                action_request_id=req.id,
                status="DENIED",
                denial_reasons=decision.reasons,
            )
        if decision.requires_approval:
            from core.domain.approvals.service import ApprovalService
            from core.domain.delivery_cycles.models import DeliveryCycle
            from core.domain.enums import ApprovalType

            cycle = await self._session.get(DeliveryCycle, execution.delivery_cycle_id)
            project_id = cycle.project_id if cycle else uuid.UUID(int=0)
            actor_row = await self._session.get(Actor, actor_id)
            if actor_row is None:
                raise ValueError("action actor missing")
            approval = await ApprovalService().request(
                self._session,
                project_id,
                execution.delivery_cycle_id,
                ApprovalType.ACTION,
                subject_type="action_request",
                subject_id=req.id,
                subject_version=1,
                subject_hash=req.params_hash,
                ctx=CommandContext(actor=actor_row, correlation_id=req.correlation_id),
            )
            req.approval_id = approval.id
            req.status = ActionStatus.PENDING_APPROVAL
            duration_ms = int((time.monotonic() - start) * 1000)
            await self._write_result(req, "PENDING_APPROVAL", None, decision.reasons, duration_ms)
            await append_domain_event(
                self._session,
                aggregate_type="action",
                aggregate_id=req.id,
                event_type="action.approval_requested",
                payload={
                    "approval_id": str(approval.id),
                    "execution_id": str(execution.id),
                    "tool": tool,
                },
                actor_id=actor_id,
                correlation_id=req.correlation_id,
                delivery_cycle_id=execution.delivery_cycle_id,
                project_id=project_id,
            )
            return GatewayToolResult(
                action_request_id=req.id,
                status="PENDING_APPROVAL",
                denial_reasons=decision.reasons,
            )

        req.status = ActionStatus.EXECUTING
        await self._session.flush()
        try:
            tctx = await self._build_tool_context(
                execution, contract, contract_row, actor_id=actor_id
            )
            handler = get_handler(tool_def.handler)
            output = await handler(tctx, params)
            req.status = ActionStatus.SUCCEEDED
            duration = int((time.monotonic() - start) * 1000)
            await self._write_result(req, "SUCCEEDED", output, [], duration)
            await append_domain_event(
                self._session,
                aggregate_type="action",
                aggregate_id=req.id,
                event_type="action.completed",
                payload={"tool": tool, "execution_id": str(execution.id)},
                actor_id=req.actor_id,
                correlation_id=req.correlation_id,
                delivery_cycle_id=execution.delivery_cycle_id,
            )
            return GatewayToolResult(action_request_id=req.id, status="SUCCEEDED", output=output)
        except (PathPolicyViolation, KeyError, ValueError) as exc:
            req.status = ActionStatus.FAILED
            duration = int((time.monotonic() - start) * 1000)
            await self._write_result(req, "FAILED", None, [str(exc)], duration, error=str(exc))
            return GatewayToolResult(
                action_request_id=req.id,
                status="FAILED",
                error=str(exc),
                denial_reasons=[str(exc)],
            )

    async def handle_system(
        self,
        actor_id: uuid.UUID,
        tool: str,
        params: dict[str, Any],
        ctx: CommandContext,
    ) -> GatewayToolResult:
        start = time.monotonic()
        tool_def = get_tool(tool) if tool in {"repo.read"} else None
        try:
            tool_def = get_tool(tool)
        except KeyError:
            return GatewayToolResult(
                action_request_id=uuid.uuid4(),
                status="DENIED",
                denial_reasons=[f"unknown tool {tool}"],
            )
        req = ActionRequest(
            key=f"AR-{uuid.uuid4().hex[:12]}",
            execution_id=None,
            lease_id=None,
            actor_id=actor_id,
            agent_profile=None,
            tool=tool,
            resource=tool_def.resource,
            action=tool_def.action,
            params=redact_params(params),
            params_hash=_params_hash(params),
            correlation_id=ctx.correlation_id,
            status=ActionStatus.EXECUTING,
        )
        self._session.add(req)
        await self._session.flush()
        try:
            handler = get_handler(tool_def.handler)
            tctx = ToolExecutionContext(
                session=self._session,
                execution_id=uuid.UUID(int=0),
                task_id=uuid.UUID(int=0),
                delivery_cycle_id=uuid.UUID(int=0),
                project_id=uuid.UUID(int=0),
                repository_id=None,
                workspace_path=None,
                workspace_branch=None,
                contract=None,
                task_contract_id=None,
                task_contract_version=None,
                execution_key="SYSTEM",
                correlation_id=ctx.correlation_id,
            )
            output = await handler(tctx, params)
            req.status = ActionStatus.SUCCEEDED
            duration = int((time.monotonic() - start) * 1000)
            await self._write_result(req, "SUCCEEDED", output, [], duration)
            return GatewayToolResult(action_request_id=req.id, status="SUCCEEDED", output=output)
        except Exception as exc:
            req.status = ActionStatus.FAILED
            duration = int((time.monotonic() - start) * 1000)
            await self._write_result(req, "FAILED", None, [str(exc)], duration, error=str(exc))
            return GatewayToolResult(action_request_id=req.id, status="FAILED", error=str(exc))

    async def _validate(
        self,
        *,
        execution: Execution,
        contract: TaskContractBody | None,
        agent_profile: str | None,
        tool: str,
        params: dict[str, Any],
        actor_kind: ActorKind,
    ) -> list[str]:
        reasons: list[str] = []
        from core.runtime.agent_profiles import get_profile

        if agent_profile:
            try:
                profile = get_profile(agent_profile)
                if tool not in profile.allowed_tools:
                    reasons.append(f"tool {tool} not in agent profile allowed_tools")
            except KeyError:
                reasons.append(f"unknown agent profile {agent_profile}")
        if contract is not None:
            allowed = contract.allowed_actions
            if allowed and tool not in allowed:
                reasons.append(f"tool {tool} not in contract allowed_actions")
            for prohibited in contract.prohibited_operations:
                if prohibited in tool or prohibited in json.dumps(params):
                    reasons.append(f"prohibited operation match: {prohibited}")
        if reasons:
            return reasons
        get_tool(tool)
        return reasons

    async def _build_tool_context(
        self,
        execution: Execution,
        contract: TaskContractBody | None,
        contract_row: TaskContract | None,
        *,
        actor_id: uuid.UUID | None = None,
    ) -> ToolExecutionContext:
        ws_result = await self._session.execute(
            select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == execution.id)
        )
        ws = ws_result.scalar_one_or_none()
        workspace_path = None
        branch = None
        repository_id = contract.repository_id if contract else None
        project_id = uuid.UUID(int=0)
        if ws is not None:
            from core.domain.repositories.models import Repository

            repo = await self._session.get(Repository, ws.repository_id)
            if repo:
                project_id = repo.project_id
                repository_id = repo.id
            from core.domain.repositories.models import RepositoryWorkspace

            canonical = None
            if repo and repo.workspace_id:
                canonical = await self._session.get(RepositoryWorkspace, repo.workspace_id)
            if canonical:
                workspace_path = self._locator.resolve(
                    canonical.storage_backend,
                    ws.logical_location,
                )
                branch = ws.branch
        return ToolExecutionContext(
            session=self._session,
            execution_id=execution.id,
            task_id=execution.task_id,
            delivery_cycle_id=execution.delivery_cycle_id,
            project_id=project_id,
            repository_id=repository_id,
            workspace_path=workspace_path,
            workspace_branch=branch,
            contract=contract,
            task_contract_id=execution.task_contract_id,
            task_contract_version=contract_row.version if contract_row else None,
            execution_key=execution.key,
            correlation_id=str(execution.id),
            actor_id=actor_id,
        )

    async def _persist_denied(
        self,
        *,
        tool: str,
        params: dict[str, Any],
        reasons: list[str],
        execution_id: uuid.UUID | None,
        actor_id: uuid.UUID,
        correlation_id: str,
        lease_id: uuid.UUID | None = None,
        contract: TaskContract | None = None,
        agent_profile: str | None = None,
    ) -> ActionRequest:
        try:
            tool_def = get_tool(tool)
        except KeyError:
            tool_def = None
        req = ActionRequest(
            key=f"AR-{uuid.uuid4().hex[:12]}",
            execution_id=execution_id,
            lease_id=lease_id,
            actor_id=actor_id,
            agent_profile=agent_profile,
            tool=tool,
            resource=tool_def.resource if tool_def else "unknown",
            action=tool_def.action if tool_def else "unknown",
            params=redact_params(params),
            params_hash=_params_hash(params),
            task_contract_id=contract.id if contract else None,
            task_contract_version=contract.version if contract else None,
            correlation_id=correlation_id,
            status=ActionStatus.DENIED,
            policy_decision={"decision": "DENY", "reasons": reasons},
        )
        self._session.add(req)
        await self._session.flush()
        await self._write_result(req, "DENIED", None, reasons, 0)
        return req

    async def _write_result(
        self,
        req: ActionRequest,
        status: str,
        output: dict[str, Any] | None,
        reasons: list[str],
        duration_ms: int,
        *,
        error: str | None = None,
    ) -> None:
        self._session.add(
            ActionResult(
                action_request_id=req.id,
                status=status,
                output=output,
                error_class="DENIED" if status == "DENIED" else None,
                error_detail=error or ("; ".join(reasons) if reasons else None),
                duration_ms=duration_ms,
            )
        )
        await self._session.flush()
