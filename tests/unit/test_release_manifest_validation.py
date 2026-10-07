"""Release manifest validation (Phase 10 §12 unit)."""

from __future__ import annotations

import uuid

import pytest
from core.integration.enums import ICStatus
from core.integration.models import IntegrationCandidate
from core.release.manifest import validate_manifest_against_ic
from core.release.schemas import ReleaseManifestContent

pytestmark = pytest.mark.unit


def _minimal_manifest(
    *,
    integrated_sha: str,
    canonical: str,
    cycle_key: str,
) -> ReleaseManifestContent:
    return ReleaseManifestContent.model_validate(
        {
            "release_key": "R1",
            "project_key": "P",
            "delivery_cycle_key": cycle_key,
            "cycle_type": "GREENFIELD_BUILD",
            "integration_candidate": {"key": "IC-1", "integrated_sha": integrated_sha},
            "repository": {"canonical_commit": canonical},
            "canonical_index_version_id": uuid.uuid4(),
            "canonical_index_hash": "0" * 64,
            "feature_specs": [],
            "implementation_specs": [],
            "acceptance": [],
            "gates": {},
            "approvals": [],
            "executions": [],
            "waived_findings": [],
            "blocking_findings": 0,
            "candidate_commits": [],
            "policy_version": "v1",
        }
    )


@pytest.mark.parametrize(
    ("ic_sha", "manifest_sha", "canonical", "manifest_cycle_key", "ic_status", "expect_ok"),
    [
        ("a" * 40, "a" * 40, "a" * 40, "DC-1", ICStatus.READY, True),
        ("a" * 40, "b" * 40, "a" * 40, "DC-1", ICStatus.READY, False),
        ("a" * 40, "a" * 40, "c" * 40, "DC-1", ICStatus.READY, False),
        ("a" * 40, "a" * 40, "a" * 40, "DC-2", ICStatus.READY, False),
        ("a" * 40, "a" * 40, "a" * 40, "DC-1", ICStatus.FAILED, False),
    ],
)
def test_validate_manifest_against_ic_truth_table(
    ic_sha: str,
    manifest_sha: str,
    canonical: str,
    manifest_cycle_key: str,
    ic_status: ICStatus,
    expect_ok: bool,
) -> None:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import DeliveryCycleType

    cycle = DeliveryCycle(
        project_id=uuid.uuid4(),
        key="DC-1",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="t",
        state="RELEASE",
        state_version=0,
        opened_by_actor_id=uuid.uuid4(),
    )
    ic = IntegrationCandidate(
        key="IC-1",
        delivery_cycle_id=cycle.id,
        repository_id=uuid.uuid4(),
        base_sha="0" * 40,
        integration_branch="integration/ic-1",
        status=ic_status,
        integrated_sha=ic_sha,
    )
    content = _minimal_manifest(
        integrated_sha=manifest_sha,
        canonical=canonical,
        cycle_key=manifest_cycle_key,
    )
    ok, reasons = validate_manifest_against_ic(content, ic, cycle)
    assert ok is expect_ok
    if not expect_ok:
        assert reasons
