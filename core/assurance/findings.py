"""Finding persistence (Phase 08 base; Phase 09 fingerprint + waiver)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.findings_policy import FindingPolicy
from core.assurance.models import Finding
from core.commands.context import CommandContext
from core.domain.approvals.service import ApprovalService
from core.domain.canonical_json import sha256_hex
from core.domain.enums import ApprovalType
from core.domain.events.append import append_domain_event
from core.domain.exceptions import DomainError, Unauthorized
from core.domain.sequences import next_project_key
from core.integration.enums import FindingSeverity, FindingSource, FindingStatus


def compute_fingerprint(
    source: str,
    category: str,
    code_refs: list[Any] | None,
) -> str:
    normalized_refs = []
    for ref in code_refs or []:
        if isinstance(ref, dict):
            normalized_refs.append(
                {
                    "file_path": ref.get("file_path"),
                    "line_start": ref.get("line_start"),
                }
            )
    payload = json.dumps(
        {"source": source, "category": category, "code_refs": normalized_refs},
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_hex(payload)


class FindingService:
    async def create(
        self,
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        source: FindingSource,
        category: str,
        severity: FindingSeverity,
        title: str,
        detail: dict[str, Any],
        ctx: CommandContext,
        integration_candidate_id: uuid.UUID | None = None,
        commit_sha: str | None = None,
        code_refs: list[Any] | None = None,
        spec_refs: list[Any] | None = None,
        producer_execution_id: uuid.UUID | None = None,
        fingerprint: str | None = None,
    ) -> Finding:
        key = await next_project_key(session, project_id, "finding", prefix="F")
        blocking = FindingPolicy().is_blocking(severity.value, category)
        fp = fingerprint or compute_fingerprint(source.value, category, code_refs)
        row = Finding(
            key=key,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            integration_candidate_id=integration_candidate_id,
            commit_sha=commit_sha,
            source=source,
            category=category,
            severity=severity,
            blocking=blocking,
            title=title,
            detail=detail,
            code_refs=code_refs or [],
            spec_refs=spec_refs or [],
            status=FindingStatus.OPEN,
            producer_execution_id=producer_execution_id,
            fingerprint=fp,
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="finding",
            aggregate_id=row.id,
            event_type="finding.created",
            payload={"key": key, "category": category, "severity": severity.value},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return row

    async def request_waiver(
        self,
        session: AsyncSession,
        finding_id: uuid.UUID,
        project_id: uuid.UUID,
        ctx: CommandContext,
    ) -> uuid.UUID:
        if ctx.actor.kind.name == "AGENT":
            raise Unauthorized("Agents cannot waive findings")
        finding = await session.get(Finding, finding_id)
        if finding is None:
            raise DomainError(code="NOT_FOUND", message="Finding not found")
        approval = await ApprovalService().request(
            session,
            project_id,
            finding.delivery_cycle_id,
            ApprovalType.FINDING_WAIVER,
            subject_type="FINDING",
            subject_id=finding.id,
            subject_version=1,
            subject_hash=finding.fingerprint or finding.key,
            ctx=ctx,
        )
        return approval.id

    async def apply_waiver(
        self,
        session: AsyncSession,
        finding_id: uuid.UUID,
        approval_id: uuid.UUID,
        ctx: CommandContext,
    ) -> Finding:
        finding = await session.get(Finding, finding_id)
        if finding is None:
            raise DomainError(code="NOT_FOUND", message="Finding not found")
        finding.status = FindingStatus.WAIVED
        finding.waiver_approval_id = approval_id
        finding.blocking = False
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="finding",
            aggregate_id=finding.id,
            event_type="finding.waived",
            payload={"approval_id": str(approval_id)},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=finding.project_id,
            delivery_cycle_id=finding.delivery_cycle_id,
        )
        return finding
