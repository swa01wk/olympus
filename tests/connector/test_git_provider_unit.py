"""Git provider connector tests (no live Gitea required)."""

from __future__ import annotations

import pytest
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.git_provider.connector import GitProviderConnector

pytestmark = pytest.mark.connector


@pytest.mark.asyncio
async def test_push_branch_denies_non_olympus_ref() -> None:
    conn = GitProviderConnector("git_provider_gitea", "GITEA")
    action = ConnectorAction(
        connector=conn.name,
        action="push_branch",
        target_resource="repo",
        inputs={
            "logical_location": "projects/x/repo",
            "ref": "refs/heads/main",
        },
        idempotency_key="test-deny-main",
        correlation_id="c1",
        expected_result_schema="PushResult",
    )
    result = await conn.execute(action)
    assert result.status == "FAILED_FINAL"
    assert result.error_class == "PROTECTED_REF"


@pytest.mark.asyncio
async def test_validate_registration_requires_https() -> None:
    conn = GitProviderConnector("git_provider_github", "GITHUB")
    action = ConnectorAction(
        connector=conn.name,
        action="validate_registration",
        target_resource="bad",
        inputs={"remote_url": "file:///tmp/x"},
        idempotency_key="validate-file",
        correlation_id="c2",
        expected_result_schema="ValidateResult",
    )
    result = await conn.execute(action)
    assert result.status == "FAILED_FINAL"
    assert result.error_class == "INVALID_URL"


@pytest.mark.asyncio
async def test_validate_registration_allows_local_gitea_http() -> None:
    conn = GitProviderConnector("git_provider_gitea", "GITEA")
    action = ConnectorAction(
        connector=conn.name,
        action="validate_registration",
        target_resource="local",
        inputs={"remote_url": "http://127.0.0.1:3000/olympus/demo.git"},
        idempotency_key="validate-local-gitea",
        correlation_id="c3",
        expected_result_schema="ValidateResult",
    )
    result = await conn.execute(action)
    assert result.status == "SUCCEEDED"
