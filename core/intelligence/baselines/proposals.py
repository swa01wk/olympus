"""Deterministic baseline proposals from observed tests and safe runtime probes."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import SpecKind, SpecStatus
from core.domain.events.append import append_domain_event
from core.domain.sequences import next_project_key
from core.intelligence.baselines.enums import (
    BaselineCheckKind,
    BaselineSource,
    BaselineStatus,
)
from core.intelligence.baselines.models import BehavioralBaseline
from core.intelligence.baselines.probes import SafeRuntimeProbeGenerator
from core.intelligence.brownfield.enums import ObservedBehaviorKind
from core.intelligence.brownfield.models import ObservedBehavior
from core.product_model.models import AcceptanceCriterion, FeatureSpec
from core.traceability.models import SpecCodeLink

_CONFIDENCE_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _confidence_ok(level: str | None) -> bool:
    if level is None:
        return False
    return _CONFIDENCE_ORDER.get(level.upper(), 0) >= _CONFIDENCE_ORDER["MEDIUM"]


class BaselineProposalService:
    async def propose_for_cycle(
        self,
        session: AsyncSession,
        cycle_id: uuid.UUID,
        ctx: CommandContext,
    ) -> list[BehavioralBaseline]:
        cycle = await session.get(DeliveryCycle, cycle_id)
        if cycle is None or cycle.base_sha is None:
            raise ValueError("cycle missing base sha")
        sha = cycle.base_sha
        specs = (
            (
                await session.execute(
                    select(FeatureSpec).where(
                        FeatureSpec.project_id == cycle.project_id,
                        FeatureSpec.spec_kind == SpecKind.RECOVERED,
                        FeatureSpec.status.in_(
                            (
                                SpecStatus.PROPOSED,
                                SpecStatus.PROMOTED,
                                SpecStatus.CONFIRMED_EXISTING,
                            )
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        eligible_specs = [s for s in specs if _confidence_ok(s.confidence)]
        behaviors = (
            (
                await session.execute(
                    select(ObservedBehavior).where(ObservedBehavior.delivery_cycle_id == cycle_id)
                )
            )
            .scalars()
            .all()
        )
        test_behaviors = [
            b
            for b in behaviors
            if b.kind
            in (
                ObservedBehaviorKind.TEST_EXECUTION,
                ObservedBehaviorKind.TEST_ASSERTED,
            )
            and (b.passed is None or b.passed is True)
        ]
        covered_ac_keys: set[tuple[uuid.UUID, str]] = set()
        created: list[BehavioralBaseline] = []
        seq = 0
        for spec in eligible_specs:
            acs = (
                (
                    await session.execute(
                        select(AcceptanceCriterion).where(
                            AcceptanceCriterion.feature_spec_id == spec.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            links = (
                (await session.execute(select(SpecCodeLink).where(SpecCodeLink.spec_id == spec.id)))
                .scalars()
                .all()
            )
            stable_keys = [link.code_stable_key for link in links]
            for ac in acs:
                if (spec.id, ac.lineage_key) in covered_ac_keys:
                    continue
                matched = _match_test_behavior(test_behaviors, stable_keys, ac)
                if matched is None:
                    continue
                seq += 1
                row = await self._create_proposed(
                    session,
                    cycle,
                    seq,
                    spec,
                    ac,
                    matched,
                    sha,
                    ctx,
                )
                created.append(row)
                covered_ac_keys.add((spec.id, ac.lineage_key))

        probe_rows = await SafeRuntimeProbeGenerator().propose(
            session,
            cycle,
            eligible_specs,
            covered_ac_keys,
            sha,
            ctx,
            start_seq=seq,
        )
        created.extend(probe_rows)
        await append_domain_event(
            session,
            aggregate_type="delivery_cycle",
            aggregate_id=cycle_id,
            event_type="baseline.proposed",
            payload={"count": len(created), "commit_sha": sha},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle_id,
        )
        return created

    async def _create_proposed(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        seq: int,
        spec: FeatureSpec,
        ac: AcceptanceCriterion,
        behavior: ObservedBehavior,
        sha: str,
        ctx: CommandContext,
    ) -> BehavioralBaseline:
        key = await next_project_key(session, cycle.project_id, "baseline", prefix="BL")
        given = ac.given or f"Recovered AC {ac.lineage_key}"
        when = ac.when or behavior.description
        then = ac.then or "Observed behavior holds at onboarding SHA"
        node_ref = _behavior_check_ref(behavior)
        row = BehavioralBaseline(
            project_id=cycle.project_id,
            lineage_key=key,
            version=1,
            status=BaselineStatus.PROPOSED,
            source=BaselineSource.BROWNFIELD_EXISTING_TEST,
            given=given,
            when=when,
            then=then,
            check_kind=BaselineCheckKind.EXISTING_TEST,
            check_ref=node_ref,
            feature_spec_id=spec.id,
            ac_lineage_key=ac.lineage_key,
            observed_behavior_ids=[str(behavior.id)],
            exercised_stable_keys=list(behavior.subject_stable_keys or []),
            established_sha=sha,
        )
        session.add(row)
        await session.flush()
        return row

    async def create_from_characterization(
        self,
        session: AsyncSession,
        cycle: DeliveryCycle,
        spec_id: uuid.UUID,
        ac_key: str,
        *,
        given: str,
        when: str,
        then: str,
        check_kind: BaselineCheckKind,
        check_ref: str,
        exercised: list[str],
        sha: str,
        ctx: CommandContext,
    ) -> BehavioralBaseline:
        key = await next_project_key(session, cycle.project_id, "baseline", prefix="BL")
        row = BehavioralBaseline(
            project_id=cycle.project_id,
            lineage_key=key,
            version=1,
            status=BaselineStatus.PROPOSED,
            source=BaselineSource.BROWNFIELD_CHARACTERIZATION,
            given=given,
            when=when,
            then=then,
            check_kind=check_kind,
            check_ref=check_ref,
            feature_spec_id=spec_id,
            ac_lineage_key=ac_key,
            observed_behavior_ids=[],
            exercised_stable_keys=exercised,
            established_sha=sha,
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="baseline",
            aggregate_id=row.id,
            event_type="baseline.proposed",
            payload={"source": "characterization", "check_ref": check_ref},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=cycle.id,
        )
        return row


def _behavior_check_ref(behavior: ObservedBehavior) -> str:
    for ref in behavior.evidence_refs or []:
        if ref.get("type") == "TEST_RESULT":
            return str(ref.get("ref", behavior.key))
    keys = behavior.subject_stable_keys or []
    if keys:
        return str(keys[0])
    return behavior.key


def _match_test_behavior(
    behaviors: list[ObservedBehavior],
    stable_keys: list[str],
    ac: AcceptanceCriterion,
) -> ObservedBehavior | None:
    ac_text = " ".join(filter(None, [ac.statement, ac.given, ac.when, ac.then])).lower()
    for behavior in behaviors:
        ref = _behavior_check_ref(behavior).lower()
        subjects = [str(s).lower() for s in (behavior.subject_stable_keys or [])]
        if any(ref in sk or sk in ref for sk in stable_keys):
            return behavior
        if any(sk in ref for sk in subjects):
            return behavior
        if ac_text and any(token in ref for token in ac_text.split() if len(token) > 4):
            return behavior
    if behaviors:
        return behaviors[0]
    return None
