from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.bus import Command, CommandBus
from core.commands.context import CommandContext
from core.domain.audit.append import append_audit
from core.domain.enums import InboundEventStatus
from core.domain.events.append import append_domain_event
from core.integrations.inbound.models import InboundEvent
from core.integrations.inbound.registry import get_inbound_registry
from core.integrations.inbound.storage import ContentAddressedStore


class InboundService:
    def __init__(self, bus: CommandBus) -> None:
        self._bus = bus
        self._registry = get_inbound_registry()

    async def receive(
        self,
        session: AsyncSession,
        adapter_name: str,
        raw: dict[str, Any],
        ctx: CommandContext,
    ) -> dict[str, Any]:
        adapter = self._registry.get(adapter_name)
        if adapter is None:
            raise ValueError(f"Unknown inbound adapter: {adapter_name}")

        ok, reason = await adapter.authenticate(session, raw, ctx)
        if not ok:
            row = await self._record_event(
                session,
                adapter.source_type,
                str(raw.get("source_id", "unknown")),
                str(raw.get("event_id") or ctx.idempotency_key or "unknown"),
                InboundEventStatus.REJECTED,
                raw,
                ctx,
                rejection_reason=reason,
            )
            await append_audit(
                session,
                actor_id=ctx.actor.id,
                actor_kind=ctx.actor.kind,
                action="inbound_event.rejected",
                target_type="inbound_event",
                target_id=str(row.id),
                correlation_id=ctx.correlation_id,
            )
            return {"status": "REJECTED", "inbound_event_id": str(row.id), "reason": reason}

        ok, reason = await adapter.validate(session, raw)
        if not ok:
            row = await self._record_event(
                session,
                adapter.source_type,
                str(raw.get("source_id", "unknown")),
                str(raw.get("event_id") or ctx.idempotency_key or "unknown"),
                InboundEventStatus.REJECTED,
                raw,
                ctx,
                rejection_reason=reason,
            )
            return {"status": "REJECTED", "inbound_event_id": str(row.id), "reason": reason}

        envelope = await adapter.normalize(session, raw)
        normalized = raw.get("_normalized") or {}

        existing = await session.execute(
            select(InboundEvent).where(
                InboundEvent.source_type == envelope.source_type,
                InboundEvent.source_id == envelope.source_id,
                InboundEvent.event_id == envelope.event_id,
            )
        )
        dup = existing.scalar_one_or_none()
        if dup is not None:
            if dup.command_log_id and dup.status == InboundEventStatus.ACCEPTED:
                from core.domain.policy.models import CommandLog

                log = await session.get(CommandLog, dup.command_log_id)
                prior_result = log.result if log else {}
                return {
                    "status": "DUPLICATE",
                    "inbound_event_id": str(dup.id),
                    "result": prior_result or {},
                    "replayed": True,
                }
            return {"status": "DUPLICATE", "inbound_event_id": str(dup.id)}

        event_row = await self._record_event(
            session,
            envelope.source_type,
            envelope.source_id,
            envelope.event_id,
            InboundEventStatus.RECEIVED,
            raw,
            ctx,
            normalized=normalized,
            project_id=envelope.project_id,
        )

        cmd_name, target_type, target_id, payload = await adapter.to_command(
            session, envelope, normalized
        )
        payload["inbound_event_id"] = str(event_row.id)

        cmd_result = await self._bus.dispatch(
            session,
            Command(
                name=cmd_name,
                target_type=target_type,
                target_id=target_id,
                payload=payload,
            ),
            ctx,
        )

        event_row.status = InboundEventStatus.ACCEPTED
        if ctx.command_log_id:
            event_row.command_log_id = ctx.command_log_id
        await session.flush()

        await append_domain_event(
            session,
            aggregate_type="inbound_event",
            aggregate_id=event_row.id,
            event_type="inbound_event.received",
            payload={"adapter": adapter_name, "status": "ACCEPTED"},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=event_row.project_id,
        )
        await append_audit(
            session,
            actor_id=ctx.actor.id,
            actor_kind=ctx.actor.kind,
            action="inbound_event.accepted",
            target_type="inbound_event",
            target_id=str(event_row.id),
            correlation_id=ctx.correlation_id,
            command_log_id=ctx.command_log_id,
        )
        return {
            "status": "ACCEPTED",
            "inbound_event_id": str(event_row.id),
            "result": cmd_result.data,
            "replayed": cmd_result.replayed,
        }

    async def _record_event(
        self,
        session: AsyncSession,
        source_type: str,
        source_id: str,
        event_id: str,
        status: InboundEventStatus,
        raw: dict[str, Any],
        ctx: CommandContext,
        *,
        rejection_reason: str | None = None,
        normalized: dict[str, Any] | None = None,
        project_id: str | None = None,
    ) -> InboundEvent:
        import uuid

        payload_bytes = json.dumps(
            {k: v for k, v in raw.items() if k not in {"file_bytes", "_normalized"}},
            default=str,
        ).encode("utf-8")
        inline = None
        storage_ref = None
        if len(payload_bytes) > 65536:
            storage_ref, _ = ContentAddressedStore().put_bytes(
                payload_bytes, prefix="inbound/events"
            )
        else:
            try:
                inline = json.loads(payload_bytes.decode("utf-8"))
            except json.JSONDecodeError:
                inline = {"raw": payload_bytes.decode("utf-8", errors="replace")}

        row = InboundEvent(
            source_type=source_type,
            source_id=source_id,
            event_id=event_id,
            status=status,
            rejection_reason=rejection_reason,
            payload_storage_ref=storage_ref,
            payload_inline=inline,
            normalized=normalized,
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=uuid.UUID(project_id) if project_id else None,
        )
        session.add(row)
        await session.flush()
        return row
