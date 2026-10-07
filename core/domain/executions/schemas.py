from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from core.domain.task_contracts.schemas import VersionedRef


class SnapshotContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task: dict[str, object]
    task_contract: dict[str, object]
    base_commit: str | None
    base_resolution: dict[str, object]
    spec_versions: list[VersionedRef] = Field(default_factory=list)
    architecture_versions: list[VersionedRef] = Field(default_factory=list)
    implementation_spec_versions: list[VersionedRef] = Field(default_factory=list)
    artifact_versions: list[VersionedRef] = Field(default_factory=list)
    baseline_versions: list[VersionedRef] = Field(default_factory=list)
    canonical_index_version_id: uuid.UUID | None = None
    repository: dict[str, object] | None = None
    policy_version: dict[str, object]
    risk_tier: str
    approvals: list[dict[str, object]] = Field(default_factory=list)
    project_name: str | None = None
    decision_items: list[str] = Field(default_factory=list)
    approved_product_summary: str = ""
    feature_specs: list[dict[str, object]] = Field(default_factory=list)
    implementation_specs_json: str = ""
    mandatory_ac_keys: str = ""
    repo_listing: str = ""
    feature_spec_key: str = ""
    feature_spec_body: str = ""
    acceptance_criteria: str = ""
    architecture_summary: str = ""
    scout_discovery_json: str = ""
    scout_index_summary: str = ""
    scout_behaviors_json: str = ""
    scout_feature_ref: str = ""
    scout_feature_draft_json: str = ""
    scout_code_excerpt: str = ""
    scout_context_manifest_hash: str = ""
    change_request_text: str = ""
    candidate_features_json: str = ""
    impact_summary: str = ""
    implementation_spec_mode: str = ""
    parent_implementation_spec_json: str = ""
    impact_assessment_json: str = ""


class ContinuationPackage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: uuid.UUID
    task_contract_ref: VersionedRef
    snapshot_hash: str
    produced_artifacts: list[VersionedRef] = Field(default_factory=list)
    progress_summary: str = ""
    pending: dict[str, object] = Field(default_factory=dict)
    resolution: dict[str, object] | None = None
    decisions: list[VersionedRef] = Field(default_factory=list)
    candidate_state: dict[str, object] | None = None
