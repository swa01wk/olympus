"""Gitea + Phase 16 connector helpers for live issue-tracker journey."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from typing import Any

import httpx
from core.assurance.enums import EvidenceType
from core.assurance.models import Evidence
from core.bootstrap.connectors import ensure_connectors_registered
from core.commands.context import CommandContext
from core.commands.registry import build_command_bus
from core.domain.enums import IntegrationAuthKind, RepositoryProvider
from core.domain.integrations.models import ExternalLink
from core.domain.repositories.models import Repository
from core.integration.models import IntegrationCandidate
from core.integrations.connectors.base import ConnectorAction
from core.integrations.connectors.registry import get_connector_registry
from core.integrations.connectors.secrets import store_secret
from core.integrations.inbound.models import IntegrationSource
from core.integrations.inbound.service import InboundService
from core.release.models import Release
from core.repositories.remote import RemoteRepositoryService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def gitea_base_url() -> str:
    return os.environ.get("OLYMPUS_GITEA_URL", "http://127.0.0.1:3000").rstrip("/")


def gitea_api_token() -> str:
    token = os.environ.get("GITEA_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("GITEA_API_TOKEN required (make integrations-seed)")
    return token


def gitea_reachable() -> bool:
    try:
        httpx.get(f"{gitea_base_url()}/api/v1/version", timeout=3.0)
        return True
    except httpx.HTTPError:
        return False


JOURNEY_OLYMPUS_SECRET_KEY = "journey-live-p16"


def ensure_journey_secret_key() -> None:
    """Encrypted secret: refs need OLYMPUS_SECRET_KEY; empty .env values do not."""
    if not os.environ.get("OLYMPUS_SECRET_KEY", "").strip():
        os.environ["OLYMPUS_SECRET_KEY"] = JOURNEY_OLYMPUS_SECRET_KEY
    from core.config.settings import clear_settings_cache

    clear_settings_cache()


async def ensure_integration_sources(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    webhook_secret: str,
    ci_secret: str = "ci-test-secret",
) -> None:
    ensure_journey_secret_key()
    await store_secret(session, "journey-webhook", webhook_secret)
    await store_secret(session, "journey-ci", ci_secret)
    for source_type, secret_ref in (
        ("issue_tracker_webhook", "secret:journey-webhook"),
        ("ci_callback", "secret:journey-ci"),
    ):
        existing = await session.execute(
            select(IntegrationSource).where(
                IntegrationSource.project_id == project_id,
                IntegrationSource.source_type == source_type,
                IntegrationSource.name == "default",
            )
        )
        if existing.scalar_one_or_none() is None:
            session.add(
                IntegrationSource(
                    project_id=project_id,
                    source_type=source_type,
                    name="default",
                    auth_kind=IntegrationAuthKind.HMAC_SHA256,
                    secret_ref=secret_ref,
                    active=True,
                )
            )
    await session.flush()


def gitea_owner_login(token: str) -> str:
    api = f"{gitea_base_url()}/api/v1"
    headers = {"Authorization": f"token {token}"}
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(f"{api}/user", headers=headers)
        resp.raise_for_status()
        return str(resp.json()["login"])


def create_gitea_repo(owner: str, repo_name: str, token: str) -> str:
    api = f"{gitea_base_url()}/api/v1"
    headers = {"Authorization": f"token {token}"}
    with httpx.Client(timeout=30.0) as client:
        check = client.get(f"{api}/repos/{owner}/{repo_name}", headers=headers)
        if check.status_code == 200:
            return f"{gitea_base_url()}/{owner}/{repo_name}.git"
        resp = client.post(
            f"{api}/user/repos",
            json={
                "name": repo_name,
                "private": False,
                "auto_init": False,
                "has_issues": True,
            },
            headers=headers,
        )
        resp.raise_for_status()
    return f"{gitea_base_url()}/{owner}/{repo_name}.git"


def _gitea_label_id(
    client: httpx.Client,
    api: str,
    owner: str,
    repo_name: str,
    token: str,
    label_name: str,
) -> int:
    """Gitea create-issue expects label IDs, not names (names 422)."""
    headers = {"Authorization": f"token {token}"}
    create = client.post(
        f"{api}/repos/{owner}/{repo_name}/labels",
        json={"name": label_name, "color": "0052cc"},
        headers=headers,
    )
    if create.status_code in (200, 201):
        return int(create.json()["id"])
    listed = client.get(f"{api}/repos/{owner}/{repo_name}/labels", headers=headers)
    listed.raise_for_status()
    for label in listed.json():
        if label.get("name") == label_name and label.get("id") is not None:
            return int(label["id"])
    if create.status_code >= 400:
        create.raise_for_status()
    raise RuntimeError(f"Gitea label {label_name!r} missing after create attempt")


def create_gitea_issue(
    owner: str,
    repo_name: str,
    token: str,
    *,
    title: str,
    body: str,
) -> tuple[int, str]:
    api = f"{gitea_base_url()}/api/v1"
    headers = {"Authorization": f"token {token}"}
    label_name = "olympus:change"
    with httpx.Client(timeout=30.0) as client:
        label_id = _gitea_label_id(client, api, owner, repo_name, token, label_name)
        resp = client.post(
            f"{api}/repos/{owner}/{repo_name}/issues",
            json={
                "title": title,
                "body": body,
                "labels": [label_id],
            },
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
    number = int(data["number"])
    external_ref = f"{owner}/{repo_name}#{number}"
    return number, external_ref


async def deliver_issue_webhook(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_id: uuid.UUID,
    owner: str,
    repo_name: str,
    issue_number: int,
    title: str,
    body: str,
    webhook_secret: str,
    event_id: str,
) -> dict[str, Any]:
    payload_body = {
        "issue": {
            "title": title,
            "body": body,
            "number": issue_number,
            "labels": [{"name": "olympus:change"}],
            "repository": {"full_name": f"{owner}/{repo_name}"},
        }
    }
    raw_body = json.dumps(payload_body).encode()
    sig = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    raw = {
        "source_id": "default",
        "event_id": event_id,
        "project_id": str(project_id),
        "json_body": payload_body,
        "headers": {"X-Gitea-Signature": f"sha256={sig}"},
        "raw_body": raw_body,
    }
    bus = build_command_bus()
    return await InboundService(bus).receive(session, "issue_tracker_webhook", raw, ctx)


async def attach_repository_to_gitea(
    session: AsyncSession,
    ctx: CommandContext,
    repository: Repository,
    remote_url: str,
    credential_ref: str = "secret:gitea-journey",
) -> Repository:
    ensure_journey_secret_key()
    await store_secret(session, "gitea-journey", gitea_api_token())
    return await RemoteRepositoryService().attach_remote(
        session,
        repository.id,
        RepositoryProvider.GITEA,
        remote_url,
        credential_ref,
        ctx,
    )


async def run_post_release_integrations(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project_id: uuid.UUID,
    repository: Repository,
    ic: IntegrationCandidate,
    release: Release,
    owner: str,
    repo_name: str,
    issue_number: int,
    ci_secret: str = "ci-test-secret",
) -> dict[str, object]:
    ensure_connectors_registered()
    ensure_journey_secret_key()
    token = gitea_api_token()
    await store_secret(session, "gitea-journey", token)
    cred_ref = "secret:gitea-journey"
    registry = get_connector_registry()
    correlation_id = f"journey-ci-{uuid.uuid4().hex[:8]}"
    integrated_sha = ic.integrated_sha
    assert integrated_sha is not None

    from core.integrations.connectors.secrets import build_credential_resolver

    cred = await build_credential_resolver(session).resolve_async(cred_ref)
    branch = ic.integration_branch.replace("refs/heads/", "")
    pr_ok = pb_ok = False
    if repository.remote_url:
        push_branch = ConnectorAction(
            connector="git_provider_gitea",
            action="push_branch",
            target_resource=str(repository.id),
            inputs={
                "logical_location": f"projects/{project_id}/repo",
                "ref": f"refs/heads/{branch}",
                "remote": "origin",
                "_credential": cred,
            },
            idempotency_key=f"journey-pr-branch:{release.id}",
            correlation_id=correlation_id,
            expected_result_schema="PushBranchResult",
        )
        pr_action = ConnectorAction(
            connector="git_provider_gitea",
            action="create_pull_request",
            target_resource=str(repository.id),
            inputs={
                "owner": owner,
                "repo": repo_name,
                "head": branch,
                "base": repository.default_branch,
                "title": f"Olympus IC {ic.key}",
                "body": f"Integration candidate for release {release.key}",
                "api_base_url": f"{gitea_base_url()}/api/v1",
                "_credential": cred,
            },
            idempotency_key=f"journey-pr:{release.id}",
            correlation_id=correlation_id,
            expected_result_schema="PullRequestResult",
        )
        pb, _ = await registry.execute_with_persistence(session, push_branch, actor_id=ctx.actor.id)
        pr, _ = await registry.execute_with_persistence(session, pr_action, actor_id=ctx.actor.id)
        pr_ok = pr.status == "SUCCEEDED"
        pb_ok = pb.status == "SUCCEEDED"

    ci_runner = os.environ.get("OLYMPUS_CI_RUNNER_URL", "http://127.0.0.1:8090")
    callback_url = os.environ.get(
        "OLYMPUS_CI_CALLBACK_URL",
        "http://127.0.0.1:8000/integrations/inbound/ci_callback",
    )
    trigger = ConnectorAction(
        connector="ci_http",
        action="trigger_verification",
        target_resource="ci",
        inputs={
            "sha": integrated_sha,
            "callback_url": callback_url,
            "callback_secret": ci_secret,
            "suite": "journey",
        },
        idempotency_key=f"journey-ci:{integrated_sha[:12]}",
        correlation_id=correlation_id,
        expected_result_schema="CiTrigger",
        policy_context={"ci_runner_url": ci_runner},
    )
    await registry.execute_with_persistence(session, trigger, actor_id=ctx.actor.id)

    ci_payload = {
        "run_id": f"journey-{integrated_sha[:8]}",
        "sha": integrated_sha,
        "status": "PASSED",
        "suite": "journey",
        "correlation_id": correlation_id,
        "project_id": str(project_id),
    }
    raw_ci = json.dumps(ci_payload).encode()
    ci_sig = hmac.new(ci_secret.encode(), raw_ci, hashlib.sha256).hexdigest()
    await InboundService(build_command_bus()).receive(
        session,
        "ci_callback",
        {
            "source_id": "default",
            "event_id": ci_payload["run_id"],
            "project_id": str(project_id),
            "json_body": ci_payload,
            "headers": {"X-Gitea-Signature": f"sha256={ci_sig}"},
            "raw_body": raw_ci,
        },
        ctx,
    )

    deploy = ConnectorAction(
        connector="deployment_local",
        action="deploy",
        target_resource=f"release:{release.id}",
        inputs={
            "project_id": str(project_id),
            "release_id": str(release.id),
            "tag": release.key,
        },
        idempotency_key=f"journey-deploy:{release.id}",
        correlation_id=correlation_id,
        expected_result_schema="DeployResult",
    )
    deploy_result, _ = await registry.execute_with_persistence(
        session, deploy, actor_id=ctx.actor.id
    )

    idem_close = f"journey-close:{issue_number}"
    comment = ConnectorAction(
        connector="issue_tracker_gitea",
        action="post_comment",
        target_resource=f"issue:{issue_number}",
        inputs={
            "owner": owner,
            "repo": repo_name,
            "issue_number": issue_number,
            "body": f"Released {release.key} at {integrated_sha[:12]}",
            "_credential": cred,
        },
        idempotency_key=idem_close,
        correlation_id=correlation_id,
        expected_result_schema="IssueComment",
        policy_context={"gitea_url": gitea_base_url()},
    )
    comment_result, _ = await registry.execute_with_persistence(
        session, comment, actor_id=ctx.actor.id
    )
    close_inputs: dict[str, object] = {
        "owner": owner,
        "repo": repo_name,
        "issue_number": issue_number,
        "_credential": cred,
    }
    if os.environ.get("MVP_CHAOS") == "1":
        fault = os.environ.get("MVP_CHAOS_ISSUE_CLOSE_FAULT")
        if fault:
            close_inputs["_fault_mode"] = fault
    close = ConnectorAction(
        connector="issue_tracker_gitea",
        action="close",
        target_resource=f"issue:{issue_number}",
        inputs=close_inputs,
        idempotency_key=f"{idem_close}:close",
        correlation_id=correlation_id,
        expected_result_schema="IssueClose",
        policy_context={"gitea_url": gitea_base_url()},
    )
    close_result, _ = await registry.execute_with_persistence(session, close, actor_id=ctx.actor.id)

    ev = await session.execute(
        select(Evidence).where(
            Evidence.project_id == project_id,
            Evidence.evidence_type == EvidenceType.EXTERNAL_CI,
            Evidence.commit_sha == integrated_sha,
        )
    )
    link = await session.execute(
        select(ExternalLink).where(
            ExternalLink.external_id == f"{owner}/{repo_name}#{issue_number}"
        )
    )
    return {
        "deploy_status": deploy_result.normalized_result,
        "comment_status": comment_result.status,
        "close_status": close_result.status,
        "external_ci_recorded": ev.scalar_one_or_none() is not None,
        "external_link": link.scalar_one_or_none() is not None,
        "correlation_id": correlation_id,
        "pr_created": pr_ok if repository.remote_url else False,
        "branch_pushed": pb_ok if repository.remote_url else False,
    }
