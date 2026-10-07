"""Outbound connector unit tests (Phase 16 §12)."""

from __future__ import annotations

import uuid

import pytest
from core.bootstrap.connectors import ensure_connectors_registered
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.outbound import (
    DeployLocalConnector,
    HttpCiConnector,
    HttpGenericConnector,
)
from core.integrations.connectors.registry import get_connector_registry, reset_connector_registry

pytestmark = pytest.mark.connector


@pytest.fixture(autouse=True)
def _connectors() -> None:
    reset_connector_registry()
    ensure_connectors_registered()


@pytest.mark.asyncio
async def test_http_generic_denies_non_allowlisted_host() -> None:
    conn = HttpGenericConnector()
    action = ConnectorAction(
        connector=conn.name,
        action="request",
        target_resource="http",
        inputs={"url": "https://evil.example.com/x", "method": "GET"},
        idempotency_key="http-1",
        correlation_id="c1",
        expected_result_schema="HttpResult",
    )
    result = await conn.execute(action)
    assert result.status == "FAILED_FINAL"
    assert result.error_class == "HOST_DENIED"


@pytest.mark.asyncio
async def test_deploy_local_deploy_and_rollback() -> None:
    conn = DeployLocalConnector()
    project_id = str(uuid.uuid4())
    r1 = str(uuid.uuid4())
    r2 = str(uuid.uuid4())
    deploy = ConnectorAction(
        connector=conn.name,
        action="deploy",
        target_resource="release",
        inputs={"project_id": project_id, "release_id": r1, "tag": "v1"},
        idempotency_key="dep-1",
        correlation_id="c2",
        expected_result_schema="DeployResult",
    )
    ok = await conn.execute(deploy)
    assert ok.status == "SUCCEEDED"
    assert ok.normalized_result["status"] == "HEALTHY"
    rollback = ConnectorAction(
        connector=conn.name,
        action="rollback",
        target_resource="release",
        inputs={"project_id": project_id, "release_id": r1, "to_release_id": r2},
        idempotency_key="dep-2",
        correlation_id="c2",
        expected_result_schema="DeployResult",
    )
    rb = await conn.execute(rollback)
    assert rb.status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_ci_http_read_status_not_executed() -> None:
    conn = HttpCiConnector()
    action = ConnectorAction(
        connector=conn.name,
        action="read_status",
        target_resource="ci",
        inputs={"run_id": "missing-run"},
        idempotency_key="ci-read",
        correlation_id="c3",
        expected_result_schema="CiRunStatus",
    )
    result = await conn.execute(action)
    if result.status == "UNKNOWN":
        pytest.skip("CI runner not reachable")
    assert result.status == "SUCCEEDED"
    assert result.normalized_result["outcome"] == "CONFIRMED_NOT_EXECUTED"


@pytest.mark.asyncio
async def test_push_release_denied_without_release_executor() -> None:
    registry = get_connector_registry()
    conn = registry.get("git_provider_gitea")
    action = ConnectorAction(
        connector=conn.name,
        action="push_release",
        target_resource="repo",
        inputs={
            "logical_location": "projects/x/repo",
            "branch": "main",
            "sha": "a" * 40,
            "tag": "v0",
        },
        idempotency_key="push-rel-deny",
        correlation_id="c4",
        expected_result_schema="PushReleaseResult",
    )
    result = await conn.execute(action)
    assert result.status == "FAILED_FINAL"
    assert result.error_class == "POLICY_DENIED"
