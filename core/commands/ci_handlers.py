"""CI callback command handler — EXTERNAL_CI evidence with SHA/correlation validation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.assurance.enums import EvidenceProducer, EvidenceResult, EvidenceType
from core.assurance.evidence import EvidenceService
from core.commands.context import CommandContext
from core.domain.connectors.models import ConnectorActionRecord
from core.domain.exceptions import DomainError
from core.domain.integrations.models import ExternalLink
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.policy.policy_service import load_policy_file


async def _sha_known_to_cycle(
    session: AsyncSession, sha: str
) -> tuple[IntegrationCandidate | None, bool]:
    ic_row = await session.execute(
        select(IntegrationCandidate)
        .where(
            IntegrationCandidate.integrated_sha == sha,
            IntegrationCandidate.status == ICStatus.READY,
        )
        .order_by(IntegrationCandidate.created_at.desc())
        .limit(1)
    )
    ic = ic_row.scalar_one_or_none()
    if ic is not None:
        return ic, True
    from core.domain.repositories.models import Repository

    repo_row = await session.execute(
        select(Repository).where(Repository.canonical_commit == sha).limit(1)
    )
    if repo_row.scalar_one_or_none() is not None:
        return None, True
    return None, False


async def handle_ingest_external_ci_result(
    session: AsyncSession,
    ctx: CommandContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    sha = str(payload["sha"])
    run_id = str(payload.get("run_id", ""))
    correlation_id = payload.get("correlation_id")
    ic, known = await _sha_known_to_cycle(session, sha)
    if not known:
        raise DomainError(code="UNKNOWN_SHA", message="SHA not known to Olympus")

    policy = load_policy_file().get("inbound", {}).get("ci", {})
    allow_unsolicited = bool(policy.get("allow_unsolicited", False))
    if correlation_id and not allow_unsolicited:
        trigger = await session.execute(
            select(ConnectorActionRecord).where(
                ConnectorActionRecord.correlation_id == str(correlation_id),
                ConnectorActionRecord.connector.in_(("ci_http", "ci_github_actions")),
                ConnectorActionRecord.action == "trigger_verification",
            )
        )
        if trigger.scalar_one_or_none() is None:
            raise DomainError(
                code="CORRELATION_MISMATCH",
                message="No matching ci.trigger_verification for correlation id",
            )

    if ic is None:
        return {"ingested": False, "reason": "RELEASE_SHA_ONLY", "sha": sha, "run_id": run_id}

    newer = await session.execute(
        select(IntegrationCandidate)
        .where(
            IntegrationCandidate.delivery_cycle_id == ic.delivery_cycle_id,
            IntegrationCandidate.status == ICStatus.READY,
            IntegrationCandidate.created_at > ic.created_at,
        )
        .limit(1)
    )
    if newer.scalar_one_or_none() is not None:
        return {"ingested": False, "status": "STALE", "sha": sha, "run_id": run_id}

    from core.domain.delivery_cycles.models import DeliveryCycle

    cycle = await session.get(DeliveryCycle, ic.delivery_cycle_id)
    if cycle is None:
        raise DomainError(code="CYCLE_MISSING", message="delivery cycle missing")

    evidence = await EvidenceService().record(
        session,
        project_id=cycle.project_id,
        delivery_cycle_id=cycle.id,
        integration_candidate_id=ic.id,
        commit_sha=sha,
        evidence_type=EvidenceType.EXTERNAL_CI,
        result=(
            EvidenceResult.PASS
            if payload.get("status", "PASSED") == "PASSED"
            else EvidenceResult.FAIL
        ),
        subject_type="integration_candidate",
        subject_id=ic.id,
        check_ref=f"external_ci:{run_id or sha[:8]}",
        producer=EvidenceProducer.CI,
        ctx=ctx,
        details={"run_id": run_id, "suite": payload.get("suite"), "correlation_id": correlation_id},
    )
    if run_id:
        session.add(
            ExternalLink(
                entity_type="evidence",
                entity_id=evidence.id,
                provider="ci",
                external_type="run",
                external_id=run_id,
                url=None,
            )
        )
        await session.flush()
    return {
        "ingested": True,
        "sha": sha,
        "run_id": run_id,
        "evidence_id": str(evidence.id),
        "evidence_key": evidence.key,
    }
