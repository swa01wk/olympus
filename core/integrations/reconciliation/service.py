"""Outbound reconciliation — resolve UNKNOWN connector outcomes before retry."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.connectors.models import ConnectorActionRecord, ConnectorResultRecord
from core.domain.events.append import append_domain_event
from core.domain.integrations.models import ReconciliationItem
from core.integrations.connectors.base import ConnectorAction, ReconciliationRequest
from core.integrations.connectors.registry import get_connector_registry
from core.policy.policy_service import load_policy_file


class ReconciliationService:
    async def checkpoint_waiting_external(
        self,
        session: AsyncSession,
        execution_id: uuid.UUID,
        connector_action_id: uuid.UUID,
    ) -> None:
        from core.domain.enums import CheckpointReason, ExecutionStatus
        from core.domain.executions.models import Checkpoint, Execution

        execution = await session.get(Execution, execution_id)
        if execution is None:
            return
        if execution.status not in {ExecutionStatus.STARTED, ExecutionStatus.LEASED}:
            return
        session.add(
            Checkpoint(
                execution_id=execution.id,
                reason=CheckpointReason.WAITING_EXTERNAL,
                pending_ref_type="connector_action",
                pending_ref_id=connector_action_id,
                continuation={"connector_action_id": str(connector_action_id)},
            )
        )
        execution.status = ExecutionStatus.CHECKPOINTED
        await session.flush()

    async def open_for_unknown(
        self,
        session: AsyncSession,
        connector_action_id: uuid.UUID,
        correlation_id: str,
    ) -> ReconciliationItem:
        action = await session.get(ConnectorActionRecord, connector_action_id)
        if action is None:
            raise ValueError("connector action missing")
        key = f"outbound:{action.connector}:{action.idempotency_key}"
        existing = await session.execute(
            select(ReconciliationItem).where(ReconciliationItem.key == key)
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            return row
        item = ReconciliationItem(
            key=key,
            kind="OUTBOUND_UNKNOWN",
            connector_action_id=connector_action_id,
            status="OPEN",
            attempts=0,
            next_attempt_at=datetime.now(UTC),
            correlation_id=correlation_id,
        )
        session.add(item)
        await session.flush()
        return item

    async def reconcile_item(
        self,
        session: AsyncSession,
        item_id: uuid.UUID,
        ctx: CommandContext,
    ) -> ReconciliationItem:
        item = await session.get(ReconciliationItem, item_id)
        if item is None or item.connector_action_id is None:
            raise ValueError("item not found")
        action = await session.get(ConnectorActionRecord, item.connector_action_id)
        if action is None:
            raise ValueError("action missing")
        item.status = "RECONCILING"
        registry = get_connector_registry()
        connector = registry.get(action.connector)
        expected = action.inputs.get("_reconcile_expected") or {}
        result = await connector.reconcile(
            ReconciliationRequest(
                connector_action_id=action.id,
                connector=action.connector,
                action=action.action,
                idempotency_key=action.idempotency_key,
                correlation_id=action.correlation_id,
                expected=expected,
            )
        )
        item.attempts += 1
        item.last_observation = {
            "status": result.status,
            "normalized": result.normalized_result,
        }
        outcome = (result.normalized_result or {}).get("outcome")
        policy = load_policy_file().get("reconciliation", {})
        max_attempts = int(policy.get("max_attempts", 8))
        if outcome == "CONFIRMED_EXECUTED" or (
            result.status == "SUCCEEDED" and outcome != "CONFIRMED_NOT_EXECUTED"
        ):
            action.status = "SUCCEEDED"
            item.status = "RESOLVED_EXECUTED"
            await self._resume_execution(session, action, ctx)
        elif outcome == "CONFIRMED_NOT_EXECUTED":
            item.status = "RESOLVED_NOT_EXECUTED"
            await self._retry_action(session, action, ctx)
        elif item.attempts >= max_attempts:
            item.status = "ESCALATED"
            await append_domain_event(
                session,
                aggregate_type="reconciliation",
                aggregate_id=item.id,
                event_type="reconciliation.escalated",
                payload={"key": item.key},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
            )
        else:
            item.status = "OPEN"
            backoff = min(300, 2**item.attempts)
            item.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff)
        await session.flush()
        return item

    async def _retry_action(
        self,
        session: AsyncSession,
        action: ConnectorActionRecord,
        ctx: CommandContext,
    ) -> None:
        registry = get_connector_registry()
        connector = registry.get(action.connector)
        retry = ConnectorAction(
            connector=action.connector,
            action=action.action,
            target_resource=action.target_resource,
            inputs=action.inputs,
            idempotency_key=action.idempotency_key,
            correlation_id=action.correlation_id,
            expected_result_schema=action.expected_result_schema,
            policy_context=action.policy_context,
        )
        result = await connector.execute(retry)
        action.status = result.status if result.status != "UNKNOWN" else "UNKNOWN"
        session.add(
            ConnectorResultRecord(
                connector_action_id=action.id,
                attempt=action.attempt + 1,
                status=result.status,
                normalized_result=result.normalized_result,
                external_ref=result.external_ref,
                error_class=result.error_class,
            )
        )

    async def _resume_execution(
        self,
        session: AsyncSession,
        action: ConnectorActionRecord,
        ctx: CommandContext,
    ) -> None:
        if action.execution_id is None:
            return
        from core.domain.enums import CheckpointReason, CheckpointResolution, ExecutionStatus
        from core.domain.executions.models import Checkpoint, Execution

        execution = await session.get(Execution, action.execution_id)
        if execution is None or execution.status != ExecutionStatus.CHECKPOINTED:
            return
        cp = await session.execute(
            select(Checkpoint)
            .where(Checkpoint.execution_id == execution.id)
            .order_by(Checkpoint.created_at.desc())
            .limit(1)
        )
        checkpoint = cp.scalar_one_or_none()
        if checkpoint and checkpoint.reason in {
            CheckpointReason.RECONCILIATION,
            CheckpointReason.WAITING_EXTERNAL,
        }:
            checkpoint.resolution = CheckpointResolution.RESUME_SAME
            execution.status = ExecutionStatus.LEASED
            await append_domain_event(
                session,
                aggregate_type="execution",
                aggregate_id=execution.id,
                event_type="execution.resumed",
                payload={"reason": "reconciliation"},
                actor_id=ctx.actor.id,
                correlation_id=ctx.correlation_id,
            )
