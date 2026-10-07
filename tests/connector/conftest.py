"""Fixtures for connector / connector_live tests (Gitea compose profile)."""

from __future__ import annotations

import os

import httpx
import pytest


def _gitea_base_url() -> str:
    return os.environ.get("OLYMPUS_GITEA_URL", "http://127.0.0.1:3000").rstrip("/")


@pytest.fixture(scope="session")
def gitea_base_url() -> str:
    url = _gitea_base_url()
    try:
        resp = httpx.get(f"{url}/api/v1/version", timeout=3.0)
        if resp.status_code != 200:
            pytest.skip(f"Gitea not healthy at {url} (status {resp.status_code})")
    except httpx.HTTPError:
        pytest.skip(f"Gitea not reachable at {url} (run: make integrations-up)")
    return url


@pytest.fixture(scope="session")
def gitea_api_token(gitea_base_url: str) -> str:
    token = os.environ.get("GITEA_API_TOKEN", "").strip()
    if token:
        return token
    pytest.skip(
        "Set GITEA_API_TOKEN (create in Gitea UI or scripts/integrations-seed.sh) "
        "for connector_live API tests"
    )


@pytest.fixture(scope="session")
def minio_endpoint() -> str:
    url = os.environ.get("OLYMPUS_MINIO_URL", "http://127.0.0.1:9000")
    try:
        httpx.get(f"{url}/minio/health/live", timeout=3.0)
    except httpx.HTTPError:
        pytest.skip(f"MinIO not reachable at {url} (run: make integrations-up)")
    return url


@pytest.fixture(scope="session")
def fault_proxy_url() -> str:
    url = os.environ.get("OLYMPUS_FAULT_PROXY_URL", "http://127.0.0.1:9099")
    try:
        httpx.get(f"{url}/health", timeout=3.0)
    except httpx.HTTPError:
        pytest.skip(f"Fault proxy not reachable at {url} (run: make integrations-up)")
    return url


@pytest.fixture(scope="session")
def ci_runner_url() -> str:
    url = os.environ.get("OLYMPUS_CI_RUNNER_URL", "http://127.0.0.1:8090")
    try:
        httpx.get(f"{url}/health", timeout=3.0)
    except httpx.HTTPError:
        pytest.skip(f"CI runner not reachable at {url} (run: make integrations-up)")
    return url
