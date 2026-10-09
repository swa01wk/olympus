from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.approvals.models import Approval
from core.domain.canonical_json import sha256_hex
from core.domain.enums import ApprovalStatus
from core.domain.executions.models import Execution, ExecutionSnapshot
from core.domain.executions.schemas import SnapshotContent
from core.domain.task_contracts.models import TaskContract
from core.domain.task_contracts.schemas import (
    VersionedRef,
    parse_task_contract_body,
)
from core.domain.tasks.models import Task
from core.execution.snapshots.base_commit import BaseCommitResolver
from core.execution.snapshots.planning_context import planning_prompt_fields_for_task
from core.execution.snapshots.product_context import (
    product_context_for_task,
    protected_test_refs,
)
from core.policy.policy_service import ensure_policy_version


def _ref_sort_key(ref: VersionedRef) -> tuple[str, str, int]:
    return (ref.ref_type, str(ref.ref_id), ref.version or 0)


class SnapshotBuilder:
    def __init__(self, *, base_resolver: BaseCommitResolver | None = None) -> None:
        self._base_resolver = base_resolver or BaseCommitResolver()

    async def preview_hash(
        self,
        session: AsyncSession,
        execution: Execution,
    ) -> str:
        task = await session.get(Task, execution.task_id)
        contract = await session.get(TaskContract, execution.task_contract_id)
        if task is None or contract is None:
            raise ValueError("execution missing task or contract")
        body = parse_task_contract_body(contract.body)
        base = await self._base_resolver.resolve(session, body, task)
        policy = await ensure_policy_version(session)
        policy_row = policy.current()
        if policy_row is None:
            raise ValueError("policy version missing")
        artifact_versions = sorted(
            [r for r in body.inputs if r.ref_type == "ARTIFACT"],
            key=_ref_sort_key,
        )
        content = SnapshotContent(
            task={
                "id": str(task.id),
                "key": task.key,
                "work_type": task.work_type.value,
                "origin": task.origin.value,
            },
            task_contract={
                "id": str(contract.id),
                "key": contract.key,
                "version": contract.version,
                "content_hash": contract.content_hash,
            },
            base_commit=base.base_commit,
            base_resolution={"policy": base.policy, "inputs": base.inputs},
            artifact_versions=artifact_versions,
            repository=base.repository,
            policy_version={
                "id": str(policy_row.id),
                "version": policy_row.version,
                "content_hash": policy_row.content_hash,
            },
            risk_tier=policy.get("risk.default_tier", "STANDARD"),
        )
        return sha256_hex(content.model_dump(mode="json"))

    async def build(
        self,
        session: AsyncSession,
        execution: Execution,
    ) -> ExecutionSnapshot:
        task = await session.get(Task, execution.task_id)
        contract = await session.get(TaskContract, execution.task_contract_id)
        if task is None or contract is None:
            raise ValueError("execution missing task or contract")
        body = parse_task_contract_body(contract.body)
        base = await self._base_resolver.resolve(session, body, task)
        policy = await ensure_policy_version(session)
        policy_row = policy.current()
        if policy_row is None:
            raise ValueError("policy version missing")

        artifact_versions = sorted(
            [r for r in body.inputs if r.ref_type == "ARTIFACT"],
            key=_ref_sort_key,
        )
        approvals: list[dict[str, object]] = []
        for approval_id in body.required_approvals:
            row = await session.get(Approval, approval_id)
            if row and row.status == ApprovalStatus.APPROVED:
                approvals.append(
                    {
                        "id": str(row.id),
                        "type": row.approval_type.value,
                        "subject_hash": row.subject_hash,
                    }
                )

        product_ctx = await product_context_for_task(session, task)
        protected_tests = (
            await protected_test_refs(session, task)
            if body.agent_profile == "forge.implementation"
            else []
        )
        planning_ctx = await planning_prompt_fields_for_task(
            session, task, agent_profile=body.agent_profile
        )
        scout_ctx: dict[str, str] = {}
        if body.agent_profile and body.agent_profile.startswith("scout."):
            from core.intelligence.recovered_specs.context import ScoutContextBuilder

            payload, manifest_hash = await ScoutContextBuilder().build(
                session, task.delivery_cycle_id
            )
            scout_ctx = {
                "scout_discovery_json": json.dumps(payload.get("discovery") or {}),
                "scout_index_summary": json.dumps(payload.get("index_entities") or [])[:8000],
                "scout_behaviors_json": json.dumps(payload.get("observed_behaviors") or []),
                "scout_context_manifest_hash": manifest_hash,
            }
            if body.agent_profile == "scout.recover_feature":
                import re

                from agents.scout.schemas import RepositorySurvey
                from sqlalchemy import select

                from core.domain.executions.models import Execution
                from core.domain.tasks.models import TaskDependency

                ref_match = re.search(r"Recover feature (\S+)", task.title)
                feature_ref = ref_match.group(1) if ref_match else ""
                scout_ctx["scout_feature_ref"] = feature_ref
                dep_row = (
                    (
                        await session.execute(
                            select(TaskDependency).where(TaskDependency.task_id == task.id)
                        )
                    )
                    .scalars()
                    .first()
                )
                survey_task_id = dep_row.depends_on_task_id if dep_row else None
                feature_draft_json = "{}"
                if survey_task_id and feature_ref:
                    exec_rows = (
                        await session.execute(
                            select(Execution).where(Execution.task_id == survey_task_id)
                        )
                    ).scalars()
                    for ex in exec_rows:
                        survey_blob = (ex.output or {}).get("survey")
                        if not survey_blob:
                            continue
                        survey = RepositorySurvey.model_validate(survey_blob)
                        for feat in survey.features:
                            if feat.ref == feature_ref:
                                feature_draft_json = json.dumps(feat.model_dump(mode="json"))
                                break
                        break
                scout_ctx["scout_feature_draft_json"] = feature_draft_json
        arch_versions = sorted(
            [r for r in body.inputs if r.ref_type == "ARCHITECTURE"],
            key=_ref_sort_key,
        )
        impl_versions = sorted(
            [r for r in body.inputs if r.ref_type == "IMPLEMENTATION_SPEC"],
            key=_ref_sort_key,
        )
        spec_versions = sorted(
            [r for r in body.inputs if r.ref_type == "FEATURE_SPEC"],
            key=_ref_sort_key,
        )
        content = SnapshotContent(
            task={
                "id": str(task.id),
                "key": task.key,
                "work_type": task.work_type.value,
                "origin": task.origin.value,
            },
            task_contract={
                "id": str(contract.id),
                "key": contract.key,
                "version": contract.version,
                "content_hash": contract.content_hash,
            },
            base_commit=base.base_commit,
            base_resolution={
                "policy": base.policy,
                "inputs": base.inputs,
            },
            artifact_versions=artifact_versions,
            spec_versions=spec_versions,
            architecture_versions=arch_versions,
            implementation_spec_versions=impl_versions,
            repository=base.repository,
            policy_version={
                "id": str(policy_row.id),
                "version": policy_row.version,
                "content_hash": policy_row.content_hash,
            },
            risk_tier=policy.get("risk.default_tier", "STANDARD"),
            approvals=approvals,
            project_name=product_ctx["project_name"],  # type: ignore[arg-type]
            decision_items=product_ctx["decision_items"],  # type: ignore[arg-type]
            approved_product_summary=str(product_ctx["approved_product_summary"]),
            feature_specs=planning_ctx.get("feature_specs") or [],  # type: ignore[arg-type]
            implementation_specs_json=str(planning_ctx.get("implementation_specs_json", "")),
            mandatory_ac_keys=str(planning_ctx.get("mandatory_ac_keys", "")),
            repo_listing=str(planning_ctx.get("repo_listing", "")),
            feature_spec_key=str(planning_ctx.get("feature_spec_key", "")),
            feature_spec_body=str(planning_ctx.get("feature_spec_body", "")),
            acceptance_criteria=str(planning_ctx.get("acceptance_criteria", "")),
            architecture_summary=str(planning_ctx.get("architecture_summary", "")),
            scout_discovery_json=scout_ctx.get("scout_discovery_json", ""),
            scout_index_summary=scout_ctx.get("scout_index_summary", ""),
            scout_behaviors_json=scout_ctx.get("scout_behaviors_json", ""),
            scout_feature_ref=scout_ctx.get("scout_feature_ref", ""),
            scout_feature_draft_json=scout_ctx.get("scout_feature_draft_json", ""),
            scout_code_excerpt=scout_ctx.get("scout_code_excerpt", ""),
            scout_context_manifest_hash=scout_ctx.get("scout_context_manifest_hash", ""),
            change_request_text=str(planning_ctx.get("change_request_text", "")),
            candidate_features_json=str(planning_ctx.get("candidate_features_json", "")),
            impact_summary=str(planning_ctx.get("impact_summary", "")),
            implementation_spec_mode=str(planning_ctx.get("implementation_spec_mode", "")),
            parent_implementation_spec_json=str(
                planning_ctx.get("parent_implementation_spec_json", "")
            ),
            impact_assessment_json=str(planning_ctx.get("impact_assessment_json", "")),
            protected_tests=protected_tests,
        )
        payload = content.model_dump(mode="json")
        raw_body = contract.body if isinstance(contract.body, dict) else {}
        embedded = raw_body.get("_snapshot")
        if isinstance(embedded, dict):
            for key, val in embedded.items():
                if isinstance(val, str):
                    payload[key] = val
                elif isinstance(val, list | dict):
                    payload[key] = json.dumps(val, indent=2)
                elif val is not None:
                    payload[key] = str(val)
        from core.security.snapshot_gate import assert_no_secrets_in_payload

        assert_no_secrets_in_payload(payload, context="execution_snapshot")
        snapshot_hash = sha256_hex(payload)
        snapshot = ExecutionSnapshot(
            execution_id=execution.id,
            task_contract_id=contract.id,
            task_contract_version=contract.version,
            task_contract_hash=contract.content_hash or "",
            base_commit=base.base_commit,
            repository_id=body.repository_id,
            policy_version_id=policy_row.id,
            risk_tier=str(payload.get("risk_tier", "STANDARD")),
            content=payload,
            snapshot_hash=snapshot_hash,
        )
        session.add(snapshot)
        await session.flush()
        from core.testing.faults import fault_point

        with fault_point("after_snapshot_persist"):
            pass
        execution.snapshot_id = snapshot.id
        await session.flush()
        return snapshot
