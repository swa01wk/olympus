from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.connectors.models import ConnectorActionRecord, ConnectorResultRecord
from core.integrations.connectors.base import (
    Connector,
    ConnectorAction,
    ConnectorHealth,
    ConnectorResult,
)


def _sanitize_connector_inputs(inputs: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in inputs.items() if key != "_credential"}


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, Connector] = {}

    def register(self, connector: Connector) -> None:
        self._connectors[connector.name] = connector

    def get(self, name: str) -> Connector:
        if name not in self._connectors:
            raise KeyError(f"Unknown connector: {name}")
        return self._connectors[name]

    def list_connectors(self) -> list[str]:
        return sorted(self._connectors)

    async def execute_with_persistence(
        self,
        session: AsyncSession,
        action: ConnectorAction,
        *,
        action_request_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> tuple[ConnectorResult, uuid.UUID]:
        from core.domain.actions.models import ActionRequest
        from core.domain.actors.models import Actor
        from core.domain.enums import ActionStatus, ActorKind

        if action_request_id is None:
            if actor_id is None:
                actor_row = await session.execute(
                    select(Actor).where(Actor.kind == ActorKind.SYSTEM).limit(1)
                )
                actor = actor_row.scalar_one()
                actor_id = actor.id
            req = ActionRequest(
                key=f"AR-{uuid.uuid4().hex[:12]}",
                execution_id=action.execution_id,
                actor_id=actor_id,
                tool=f"connector.{action.connector}",
                resource="connector",
                action=action.action,
                params=_sanitize_connector_inputs(action.inputs),
                params_hash=str(uuid.uuid4()),
                correlation_id=action.correlation_id,
                status=ActionStatus.EXECUTING,
            )
            session.add(req)
            await session.flush()
            action_request_id = req.id
        existing = await session.execute(
            select(ConnectorActionRecord).where(
                ConnectorActionRecord.connector == action.connector,
                ConnectorActionRecord.idempotency_key == action.idempotency_key,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None and row.status == "SUCCEEDED":
            result_row = await session.execute(
                select(ConnectorResultRecord)
                .where(ConnectorResultRecord.connector_action_id == row.id)
                .order_by(ConnectorResultRecord.received_at.desc())
                .limit(1)
            )
            stored = result_row.scalar_one_or_none()
            if stored and stored.normalized_result is not None:
                return (
                    ConnectorResult(
                        status="SUCCEEDED",
                        normalized_result=stored.normalized_result,
                        external_ref=stored.external_ref,
                    ),
                    row.id,
                )

        if row is None:
            row = ConnectorActionRecord(
                connector=action.connector,
                action=action.action,
                action_request_id=action_request_id,
                execution_id=action.execution_id,
                task_contract_ref=action.task_contract_version,
                target_resource=action.target_resource,
                inputs=_sanitize_connector_inputs(action.inputs),
                idempotency_key=action.idempotency_key,
                correlation_id=action.correlation_id,
                policy_context=action.policy_context,
                expected_result_schema=action.expected_result_schema,
                status="PENDING",
            )
            session.add(row)
            await session.flush()

        connector = self.get(action.connector)
        from core.observability.instrumentation import connector_span

        with connector_span(
            connector=action.connector,
            action=action.action,
            connector_action_id=str(row.id),
            execution_id=str(action.execution_id) if action.execution_id else None,
            correlation_id=action.correlation_id,
        ):
            result = await connector.execute(action)
        row.status = result.status if result.status != "UNKNOWN" else "UNKNOWN"
        row.external_ref = result.external_ref
        session.add(
            ConnectorResultRecord(
                connector_action_id=row.id,
                attempt=row.attempt,
                status=result.status,
                normalized_result=result.normalized_result,
                external_ref=result.external_ref,
                error_class=result.error_class,
            )
        )
        if result.status == "SUCCEEDED":
            row.status = "SUCCEEDED"
        elif result.status == "UNKNOWN":
            row.status = "UNKNOWN"
            from core.integrations.reconciliation.service import ReconciliationService

            recon = ReconciliationService()
            await recon.open_for_unknown(session, row.id, action.correlation_id)
            if action.execution_id is not None:
                await recon.checkpoint_waiting_external(session, action.execution_id, row.id)
        await session.flush()
        return result, row.id

    async def validate_all(self) -> dict[str, ConnectorHealth]:
        out: dict[str, ConnectorHealth] = {}
        for name, connector in self._connectors.items():
            out[name] = await connector.validate()
        return out


_GLOBAL: ConnectorRegistry | None = None


def get_connector_registry() -> ConnectorRegistry:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = ConnectorRegistry()
    return _GLOBAL


def reset_connector_registry() -> None:
    global _GLOBAL
    _GLOBAL = None
