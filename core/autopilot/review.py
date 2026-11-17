"""The person's review of what onboarding learned about an existing codebase.

Onboarding (BROWNFIELD_ONBOARDING) recovers features, an architecture, implementation specs,
behavioral baselines and open uncertainties. Each one needs a human promotion decision before
the project can be declared ready. This module turns that review queue into plain-language
items with a suggested decision, and applies the person's choices.

Every decision here is made with the person's own context: Autopilot only *suggests*.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import SpecStatus
from core.domain.exceptions import DomainError

KEEP = "keep"
DROP = "drop"

# subject_type → (decision when kept, decision when dropped)
_DECISIONS: dict[str, tuple[str, str]] = {
    "FEATURE_SPEC": ("PROMOTE_AS_CANONICAL", "REJECT_AS_NOT_INTENDED"),
    "IMPLEMENTATION_SPEC": ("PROMOTE_AS_CANONICAL", "REJECT_AS_NOT_INTENDED"),
    "ARCHITECTURE": ("APPROVE_AS_PROJECT_ARCHITECTURE", "REJECT_AS_NOT_INTENDED"),
    "BASELINE": ("ACTIVATE", "REJECT_AS_NOT_INTENDED"),
    "UNCERTAINTY": ("ACCEPT_KNOWN_GAP", "DEFER"),
}

_GROUPS = {
    "FEATURE_SPEC": "Features",
    "ARCHITECTURE": "Architecture",
    "IMPLEMENTATION_SPEC": "How features are built",
    "BASELINE": "Current behavior to protect",
    "UNCERTAINTY": "Open questions",
}

_KEEP_LABELS = {
    "FEATURE_SPEC": "Yes, this is a feature",
    "IMPLEMENTATION_SPEC": "Yes, keep this",
    "ARCHITECTURE": "Yes, this is the architecture",
    "BASELINE": "Protect this behavior",
    "UNCERTAINTY": "Fine, leave it open",
}

_DROP_LABELS = {
    "FEATURE_SPEC": "No, not a real feature",
    "IMPLEMENTATION_SPEC": "No, drop it",
    "ARCHITECTURE": "No, that's wrong",
    "BASELINE": "Don't protect it",
    "UNCERTAINTY": "Decide later",
}


@dataclass(frozen=True)
class ReviewItem:
    subject_type: str
    subject_id: str
    group: str
    title: str
    detail: str | None
    suggestion: str  # KEEP or DROP
    why: str | None
    keep_label: str
    drop_label: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "group": self.group,
            "title": self.title,
            "detail": self.detail,
            "suggestion": self.suggestion,
            "why": self.why,
            "keep_label": self.keep_label,
            "drop_label": self.drop_label,
        }


async def pending_items(session: AsyncSession, cycle_id: uuid.UUID) -> list[ReviewItem]:
    """Undecided review-queue entries with plain titles and a suggested choice."""
    from core.intelligence.baselines.service import BaselineService

    queue = await BaselineService().review_queue(session, cycle_id)
    pending = [q for q in queue if not q["decided"] and q["subject_type"] in _DECISIONS]
    kept_lineages: set[str] = set()
    items: list[ReviewItem] = []
    for raw in pending:
        items.append(await _describe(session, raw, kept_lineages))
    return items


async def _describe(
    session: AsyncSession, raw: dict[str, Any], kept_lineages: set[str]
) -> ReviewItem:
    from core.intelligence.baselines.models import BehavioralBaseline
    from core.planning.models import ImplementationSpec
    from core.product_model.models import FeatureSpec

    subject_type = str(raw["subject_type"])
    subject_id = uuid.UUID(str(raw["subject_id"]))
    detail_in = raw.get("detail") or {}
    title = str(detail_in.get("lineage_key") or subject_type.replace("_", " ").title())
    detail: str | None = None
    suggestion = KEEP
    why: str | None = None

    if subject_type == "FEATURE_SPEC":
        spec = await session.get(FeatureSpec, subject_id)
        if spec is not None:
            body = spec.body or {}
            title = str(body.get("summary") or spec.lineage_key)
            detail = str(body.get("behavior") or "") or None
            if spec.lineage_key in kept_lineages:
                suggestion, why = DROP, "Looks like a duplicate of another feature."
            kept_lineages.add(spec.lineage_key)
            if spec.confidence and spec.confidence.upper() == "LOW" and suggestion == KEEP:
                why = "Olympus is not very sure about this one."
    elif subject_type == "IMPLEMENTATION_SPEC":
        impl = await session.get(ImplementationSpec, subject_id)
        if impl is not None:
            body = impl.body or {}
            title = str(body.get("summary") or impl.lineage_key)
            files = body.get("file_scope") or []
            detail = f"{len(files)} files" if isinstance(files, list) and files else None
            key = f"impl:{impl.lineage_key}"
            if key in kept_lineages:
                suggestion, why = DROP, "Looks like a duplicate."
            kept_lineages.add(key)
    elif subject_type == "ARCHITECTURE":
        title = "The overall structure of your app"
    elif subject_type == "BASELINE":
        baseline = await session.get(BehavioralBaseline, subject_id)
        title = str(detail_in.get("check_ref") or detail_in.get("lineage_key") or "A behavior")
        if baseline is None or baseline.established_evidence_id is None:
            suggestion, why = DROP, "No passing test proves this behavior yet."
        else:
            detail = "Checked by a test that passes on your current code."
    elif subject_type == "UNCERTAINTY":
        title = str(detail_in.get("statement") or "Something Olympus could not work out")

    return ReviewItem(
        subject_type=subject_type,
        subject_id=str(subject_id),
        group=_GROUPS[subject_type],
        title=title[:300],
        detail=detail[:500] if detail else None,
        suggestion=suggestion,
        why=why,
        keep_label=_KEEP_LABELS[subject_type],
        drop_label=_DROP_LABELS[subject_type],
    )


async def apply_choices(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    choices: dict[tuple[str, str], str] | None,
    human_ctx: CommandContext,
) -> int:
    """Record the person's decisions; items without a choice take the suggestion.

    Returns how many decisions were recorded. Baselines proven by passing evidence on the
    current code are activated afterwards, as the person's action.
    """
    from core.intelligence.recovered_specs.promotion import PromotionService

    cycle = await session.get(DeliveryCycle, cycle_id)
    if cycle is None:
        raise DomainError(code="NOT_FOUND", message="Delivery cycle not found")
    items = await pending_items(session, cycle_id)
    if not items:
        return 0
    promotions = PromotionService()
    recorded = 0
    for item in items:
        choice = (choices or {}).get((item.subject_type, item.subject_id), item.suggestion)
        if choice not in (KEEP, DROP):
            raise DomainError(code="INVALID_CHOICE", message=f"Unknown choice {choice}")
        keep, drop = _DECISIONS[item.subject_type]
        await promotions.decide(
            session,
            cycle_id,
            item.subject_type,
            uuid.UUID(item.subject_id),
            keep if choice == KEEP else drop,
            None,
            human_ctx,
        )
        recorded += 1
    await _activate_proven_baselines(session, cycle, human_ctx)
    return recorded


async def _activate_proven_baselines(
    session: AsyncSession, cycle: DeliveryCycle, human_ctx: CommandContext
) -> None:
    from core.assurance.enums import EvidenceResult
    from core.assurance.models import Evidence
    from core.domain.repositories.models import Repository
    from core.intelligence.baselines.enums import BaselineStatus
    from core.intelligence.baselines.models import BehavioralBaseline
    from core.intelligence.baselines.service import BaselineService
    from core.product_model.models import FeatureSpec

    svc = BaselineService()
    kept = (
        await session.execute(
            select(FeatureSpec.id).where(
                FeatureSpec.project_id == cycle.project_id,
                FeatureSpec.status.in_(
                    [SpecStatus.APPROVED, SpecStatus.PROMOTED, SpecStatus.CONFIRMED_EXISTING]
                ),
            )
        )
    ).scalars()
    for spec_id in kept:
        await svc.try_auto_activate_for_spec(session, spec_id, human_ctx)

    repo = await session.get(Repository, cycle.repository_id) if cycle.repository_id else None
    canonical = repo.canonical_commit if repo else None
    if canonical is None:
        return
    proposed = (
        await session.execute(
            select(BehavioralBaseline).where(
                BehavioralBaseline.project_id == cycle.project_id,
                BehavioralBaseline.status == BaselineStatus.PROPOSED,
                BehavioralBaseline.established_sha == canonical,
            )
        )
    ).scalars()
    for baseline in proposed:
        if baseline.established_evidence_id is None:
            continue
        evidence = await session.get(Evidence, baseline.established_evidence_id)
        if evidence is not None and evidence.result == EvidenceResult.PASS:
            await svc.activate_human(session, baseline.id, human_ctx)
