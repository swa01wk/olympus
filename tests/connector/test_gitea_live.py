"""Live Gitea checks (connector_live; requires make integrations-up + GITEA_API_TOKEN)."""

from __future__ import annotations

import httpx
import pytest

pytestmark = [pytest.mark.connector, pytest.mark.connector_live]


def test_gitea_version_endpoint(gitea_base_url: str) -> None:
    resp = httpx.get(f"{gitea_base_url}/api/v1/version", timeout=5.0)
    assert resp.status_code == 200
    assert "version" in resp.json()


def test_gitea_authenticated_user(gitea_base_url: str, gitea_api_token: str) -> None:
    resp = httpx.get(
        f"{gitea_base_url}/api/v1/user",
        headers={"Authorization": f"token {gitea_api_token}"},
        timeout=5.0,
    )
    assert resp.status_code == 200
    assert resp.json().get("login")
