from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import SpecStatus
from core.domain.tasks.models import Task
from core.planning.models import ImplementationSpec
from core.product_model.models import AcceptanceCriterion, FeatureSpec, ScopeSet, ScopeSetItem


async def planning_prompt_fields_for_task(
    session: AsyncSession,
    task: Task,
    *,
    agent_profile: str | None,
) -> dict[str, object]:
    if not agent_profile or not agent_profile.startswith("kira."):
        return {}

    cycle = await session.get(DeliveryCycle, task.delivery_cycle_id)
    if cycle is None:
        return {}

    out: dict[str, object] = {
        "implementation_specs_json": "",
        "mandatory_ac_keys": "",
        "repo_listing": "(repository provisioned; use implementation spec file_scope)",
        "feature_spec_key": "",
        "feature_spec_body": "",
        "acceptance_criteria": "",
        "architecture_summary": "",
        "feature_specs": [],
    }

    if agent_profile == "kira.change_interpret":
        from core.product_model.changes.service import ChangeRequestService

        ctx_data = await ChangeRequestService().build_interpretation_context(
            session, task.delivery_cycle_id
        )
        out["change_request_text"] = str(ctx_data.get("change_request_text", ""))
        out["candidate_features_json"] = json.dumps(ctx_data.get("candidates") or [], indent=2)
        out["architecture_summary"] = str(ctx_data.get("architecture_summary", ""))

    if agent_profile == "atlas.architecture_delta":
        from core.intelligence.impact.engine import ImpactEngine

        ia = await ImpactEngine().latest_complete(session, task.delivery_cycle_id)
        out["impact_summary"] = json.dumps(
            {"architecture_delta_suggested": ia.architecture_delta_suggested if ia else False},
            indent=2,
        )
        from core.planning.models import Architecture

        arch = await session.execute(
            select(Architecture)
            .where(
                Architecture.project_id == cycle.project_id,
                Architecture.status == SpecStatus.APPROVED,
            )
            .order_by(Architecture.version.desc())
            .limit(1)
        )
        arch_row = arch.scalar_one_or_none()
        if arch_row is not None:
            out["architecture_summary"] = json.dumps(arch_row.body or {}, indent=2)

    if agent_profile == "kira.implementation_spec":
        from core.domain.enums import DeliveryCycleType

        if cycle.type == DeliveryCycleType.FEATURE_CHANGE:
            out["implementation_spec_mode"] = "DELTA"

    if agent_profile == "kira.implementation_spec" and task.governing_ref_id:
        spec = await session.get(FeatureSpec, task.governing_ref_id)
        if spec is not None:
            out["feature_spec_key"] = spec.lineage_key
            out["feature_spec_body"] = json.dumps(spec.body or {}, indent=2)
            acs = await session.execute(
                select(AcceptanceCriterion).where(AcceptanceCriterion.feature_spec_id == spec.id)
            )
            out["acceptance_criteria"] = json.dumps(
                [
                    {
                        "key": a.lineage_key,
                        "statement": a.statement,
                        "mandatory": a.mandatory,
                    }
                    for a in acs.scalars()
                ],
                indent=2,
            )
        from core.planning.models import Architecture, ArchitectureContract

        arch = await session.execute(
            select(Architecture)
            .where(
                Architecture.project_id == cycle.project_id,
                Architecture.status == SpecStatus.APPROVED,
            )
            .limit(1)
        )
        arch_row = arch.scalar_one_or_none()
        if arch_row is not None:
            body = arch_row.body or {}
            contract_rows = await session.execute(
                select(ArchitectureContract).where(
                    ArchitectureContract.architecture_id == arch_row.id
                )
            )
            contracts = [
                {
                    "key": c.key,
                    "kind": c.kind,
                    "name": c.name,
                    "definition": c.definition,
                }
                for c in contract_rows.scalars()
            ]
            components_raw = body.get("components")
            components: list[Any] = components_raw if isinstance(components_raw, list) else []
            comp_names = [
                c.get("name") for c in components if isinstance(c, dict) and c.get("name")
            ]
            decisions_raw = body.get("decisions")
            decisions: list[Any] = decisions_raw if isinstance(decisions_raw, list) else []
            decision_ids = [d.get("id") for d in decisions if isinstance(d, dict) and d.get("id")]
            contract_keys = [c["key"] for c in contracts]
            out["architecture_summary"] = json.dumps(
                {
                    "architecture_body": body,
                    "contracts": contracts,
                    "valid_component_names": comp_names,
                    "valid_contract_keys": contract_keys,
                    "valid_architecture_refs": sorted(
                        set(comp_names) | set(contract_keys) | set(decision_ids)
                    ),
                    "file_scope_rules": (
                        "Use prefix globs only: directory/** or directory/*.py "
                        "(not single-segment * like app/api/*)."
                    ),
                },
                indent=2,
            )

        if str(out.get("implementation_spec_mode")) == "DELTA" and spec is not None:
            from core.intelligence.impact.engine import ImpactEngine
            from core.intelligence.impact.models import ImpactItem
            from core.planning.implementation_specs.delta import resolve_parent_implementation_spec

            parent = await resolve_parent_implementation_spec(
                session,
                project_id=cycle.project_id,
                feature_spec_id=spec.id,
            )
            if parent is not None:
                out["parent_implementation_spec_json"] = json.dumps(
                    {
                        "lineage_key": parent.lineage_key,
                        "version": parent.version,
                        "kind": parent.kind,
                        "body": parent.body or {},
                    },
                    indent=2,
                )
            ia = await ImpactEngine().latest_complete(session, cycle.id)
            if ia is not None:
                impact_rows = list(
                    (
                        await session.execute(
                            select(ImpactItem).where(ImpactItem.impact_assessment_id == ia.id)
                        )
                    ).scalars()
                )
                out["impact_assessment_json"] = json.dumps(
                    [
                        {
                            "ref": row.ref,
                            "path": row.path,
                            "impact_kind": row.impact_kind,
                            "contract_surface": row.contract_surface,
                            "rationale": row.rationale,
                        }
                        for row in impact_rows
                    ],
                    indent=2,
                )

    if agent_profile == "kira.task_plan":
        impl_rows = await session.execute(
            select(ImplementationSpec).where(
                ImplementationSpec.project_id == cycle.project_id,
                ImplementationSpec.status == SpecStatus.APPROVED,
            )
        )
        impl_list = [
            {
                "lineage_key": r.lineage_key,
                "version": r.version,
                "summary": (r.body or {}).get("summary", ""),
                "file_scope": (r.body or {}).get("file_scope", []),
            }
            for r in impl_rows.scalars()
        ]
        out["implementation_specs_json"] = json.dumps(impl_list, indent=2)

        mandatory: list[str] = []
        scope = await session.execute(
            select(ScopeSet)
            .where(ScopeSet.delivery_cycle_id == cycle.id)
            .order_by(ScopeSet.created_at.desc())
            .limit(1)
        )
        scope_set = scope.scalar_one_or_none()
        if scope_set:
            items = await session.execute(
                select(ScopeSetItem).where(ScopeSetItem.scope_set_id == scope_set.id)
            )
            for item in items.scalars():
                acs = await session.execute(
                    select(AcceptanceCriterion).where(
                        AcceptanceCriterion.feature_spec_id == item.feature_spec_id,
                        AcceptanceCriterion.mandatory.is_(True),
                    )
                )
                mandatory.extend(a.lineage_key for a in acs.scalars())
        out["mandatory_ac_keys"] = json.dumps(sorted(set(mandatory)), indent=2)

        specs = await session.execute(
            select(FeatureSpec).where(
                FeatureSpec.project_id == cycle.project_id,
                FeatureSpec.status == SpecStatus.APPROVED,
            )
        )
        out["feature_specs"] = [
            {"lineage_key": s.lineage_key, "body": s.body} for s in specs.scalars()
        ]

    if agent_profile == "atlas.propose_architecture":
        specs = await session.execute(
            select(FeatureSpec).where(
                FeatureSpec.project_id == cycle.project_id,
                FeatureSpec.status == SpecStatus.APPROVED,
            )
        )
        out["feature_specs"] = [
            {"lineage_key": s.lineage_key, "body": s.body} for s in specs.scalars()
        ]

    return out
