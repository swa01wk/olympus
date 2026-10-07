"""Phase 16 outbound connectors: CI, artifact, issue tracker, deploy, HTTP."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

import httpx

from core.config.settings import get_settings
from core.execution.artifacts import ArtifactStore
from core.integrations.connectors.base import (
    ConnectorAction,
    ConnectorHealth,
    ConnectorResult,
    ReconciliationRequest,
)
from core.policy.policy_service import load_policy_file
from core.repositories.credentials import ResolvedCredential


def _idem_marker(idempotency_key: str) -> str:
    return f"<!-- olympus:idem={idempotency_key} -->"


class HttpCiConnector:
    name = "ci_http"
    actions = {"trigger_verification", "read_status"}

    def _base_url(self, action: ConnectorAction) -> str:
        return str(
            action.policy_context.get("ci_runner_url")
            or os.environ.get("OLYMPUS_CI_RUNNER_URL", "http://127.0.0.1:8090")
        ).rstrip("/")

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        if action.action == "read_status":
            run_id = str(action.inputs["run_id"])
            base = self._base_url(action)
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(f"{base}/v1/runs/{run_id}")
                if resp.status_code == 404:
                    return ConnectorResult(
                        status="SUCCEEDED",
                        normalized_result={"outcome": "CONFIRMED_NOT_EXECUTED", "run_id": run_id},
                    )
                if resp.status_code != 200:
                    return ConnectorResult(status="UNKNOWN", error_class="CI_STATUS")
                data = resp.json()
                return ConnectorResult(
                    status="SUCCEEDED",
                    normalized_result={
                        "outcome": "CONFIRMED_EXECUTED",
                        "run_id": run_id,
                        "status": data.get("status"),
                    },
                    external_ref=run_id,
                )
            except httpx.HTTPError:
                return ConnectorResult(status="UNKNOWN", error_class="CI_NETWORK")

        if action.action != "trigger_verification":
            return ConnectorResult(
                status="FAILED_FINAL", error_class="UNKNOWN_ACTION", error_detail=action.action
            )
        base = self._base_url(action)
        payload = {
            "sha": str(action.inputs["sha"]),
            "correlation_id": action.correlation_id,
            "callback_url": str(action.inputs["callback_url"]),
            "suite": str(action.inputs.get("suite", "default")),
            "secret": str(action.inputs.get("callback_secret", "ci-test-secret")),
        }
        fault = action.inputs.get("_fault_mode")
        headers: dict[str, str] = {}
        url = f"{base}/v1/trigger"
        if fault:
            proxy = os.environ.get("OLYMPUS_FAULT_PROXY_URL", "http://127.0.0.1:9099")
            headers["X-Olympus-Target"] = base
            headers["X-Olympus-Fault"] = str(fault)
            url = f"{proxy}/v1/trigger"
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError:
            return ConnectorResult(status="UNKNOWN", error_class="CI_NETWORK")
        if resp.status_code == 504 and fault == "timeout_after_forward":
            return ConnectorResult(status="UNKNOWN", error_class="CI_TIMEOUT_AFTER_FORWARD")
        if resp.status_code >= 500:
            return ConnectorResult(status="FAILED_RETRYABLE", error_class="CI_5XX")
        if resp.status_code >= 400:
            return ConnectorResult(
                status="FAILED_FINAL", error_class="CI_4XX", error_detail=resp.text[:200]
            )
        data = resp.json()
        run_id = str(data.get("run_id", ""))
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"run_id": run_id, "callback_status": data.get("callback_status")},
            external_ref=run_id,
        )

    async def reconcile(self, request: ReconciliationRequest) -> ConnectorResult:
        run_id = str(request.expected.get("run_id", ""))
        if not run_id:
            return ConnectorResult(status="UNKNOWN", error_class="MISSING_RUN_ID")
        action = ConnectorAction(
            connector=self.name,
            action="read_status",
            target_resource="ci",
            inputs={"run_id": run_id},
            idempotency_key=request.idempotency_key,
            correlation_id=request.correlation_id,
            expected_result_schema="CiRunStatus",
        )
        return await self.execute(action)

    async def validate(self) -> ConnectorHealth:
        base = os.environ.get("OLYMPUS_CI_RUNNER_URL", "http://127.0.0.1:8090")
        try:
            httpx.get(f"{base}/health", timeout=3.0)
        except httpx.HTTPError:
            return ConnectorHealth(ok=False, message="CI runner unreachable")
        return ConnectorHealth(ok=True, message="ci_http ready")


class GithubActionsCiConnector:
    name = "ci_github_actions"
    actions = {"trigger_verification", "read_status"}

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        token = get_settings().github_token.get_secret_value()
        if not token:
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="NOT_CONFIGURED",
                error_detail="GITHUB_TOKEN required for github_actions",
            )
        if action.action == "trigger_verification":
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="NOT_IMPLEMENTED",
                error_detail="workflow_dispatch wiring is optional; use ci_http in dev",
            )
        return ConnectorResult(status="FAILED_FINAL", error_class="UNKNOWN_ACTION")

    async def reconcile(self, request: ReconciliationRequest) -> ConnectorResult:
        del request
        return ConnectorResult(status="UNKNOWN", error_class="NOT_IMPLEMENTED")

    async def validate(self) -> ConnectorHealth:
        token = get_settings().github_token.get_secret_value()
        if token:
            return ConnectorHealth(ok=True, message="ci_github_actions (token present)")
        return ConnectorHealth(ok=False, message="GITHUB_TOKEN not set")


class ArtifactFsConnector:
    name = "artifact_fs"
    actions = {"publish", "read"}

    def _publish_root(self) -> Path:
        root = get_settings().olympus_storage_root / "published"
        root.mkdir(parents=True, exist_ok=True)
        return root

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        store = ArtifactStore()
        if action.action == "publish":
            artifact_id = uuid.UUID(str(action.inputs["artifact_id"]))
            from sqlalchemy.ext.asyncio import AsyncSession

            session = action.inputs.get("_session")
            if not isinstance(session, AsyncSession):
                return ConnectorResult(
                    status="FAILED_FINAL", error_class="SESSION", error_detail="missing _session"
                )
            from core.domain.artifacts.models import Artifact

            row = await session.get(Artifact, artifact_id)
            if row is None:
                return ConnectorResult(status="FAILED_FINAL", error_class="NOT_FOUND")
            raw = store.read_bytes(row)
            dest = self._publish_root() / row.content_hash
            if not dest.exists():
                dest.write_bytes(raw)
            uri = f"file://{dest}"
            return ConnectorResult(
                status="SUCCEEDED",
                normalized_result={"uri": uri, "content_hash": row.content_hash},
                external_ref=row.content_hash,
            )
        if action.action == "read":
            content_hash = str(action.inputs["content_hash"])
            path = self._publish_root() / content_hash
            if not path.is_file():
                return ConnectorResult(status="FAILED_FINAL", error_class="NOT_FOUND")
            return ConnectorResult(
                status="SUCCEEDED",
                normalized_result={"content_hash": content_hash, "size": path.stat().st_size},
            )
        return ConnectorResult(status="FAILED_FINAL", error_class="UNKNOWN_ACTION")

    async def reconcile(self, request: ReconciliationRequest) -> ConnectorResult:
        content_hash = str(request.expected.get("content_hash", ""))
        path = self._publish_root() / content_hash
        if path.is_file():
            return ConnectorResult(
                status="SUCCEEDED",
                normalized_result={"outcome": "CONFIRMED_EXECUTED", "content_hash": content_hash},
            )
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"outcome": "CONFIRMED_NOT_EXECUTED", "content_hash": content_hash},
        )

    async def validate(self) -> ConnectorHealth:
        self._publish_root()
        return ConnectorHealth(ok=True, message="artifact_fs ready")


class ArtifactS3Connector:
    name = "artifact_s3"
    actions = {"publish", "read"}

    def _minio(self) -> tuple[str, str, str, str]:
        endpoint = os.environ.get("OLYMPUS_MINIO_URL", "http://127.0.0.1:9000").rstrip("/")
        bucket = os.environ.get("OLYMPUS_MINIO_BUCKET", "olympus-artifacts")
        user = os.environ.get("OLYMPUS_MINIO_ACCESS_KEY", "minioadmin")
        password = os.environ.get("OLYMPUS_MINIO_SECRET_KEY", "minioadmin")
        return endpoint, bucket, user, password

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        endpoint, bucket, user, password = self._minio()
        if action.action == "publish":
            content_hash = str(action.inputs["content_hash"])
            body = bytes(action.inputs.get("body") or b"")
            if not body:
                return ConnectorResult(status="FAILED_FINAL", error_class="EMPTY_BODY")
            url = f"{endpoint}/{bucket}/{content_hash}"
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.put(url, content=body, auth=(user, password))
            except httpx.HTTPError:
                return ConnectorResult(status="UNKNOWN", error_class="S3_NETWORK")
            if resp.status_code not in (200, 201):
                return ConnectorResult(
                    status="FAILED_RETRYABLE",
                    error_class="S3_PUT",
                    error_detail=str(resp.status_code),
                )
            return ConnectorResult(
                status="SUCCEEDED",
                normalized_result={"uri": f"s3://{bucket}/{content_hash}"},
                external_ref=content_hash,
            )
        if action.action == "read":
            content_hash = str(action.inputs["content_hash"])
            url = f"{endpoint}/{bucket}/{content_hash}"
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.head(url, auth=(user, password))
            except httpx.HTTPError:
                return ConnectorResult(status="UNKNOWN", error_class="S3_NETWORK")
            if resp.status_code == 404:
                return ConnectorResult(status="FAILED_FINAL", error_class="NOT_FOUND")
            return ConnectorResult(
                status="SUCCEEDED",
                normalized_result={"content_hash": content_hash},
            )
        return ConnectorResult(status="FAILED_FINAL", error_class="UNKNOWN_ACTION")

    async def reconcile(self, request: ReconciliationRequest) -> ConnectorResult:
        content_hash = str(request.expected.get("content_hash", ""))
        endpoint, bucket, user, password = self._minio()
        url = f"{endpoint}/{bucket}/{content_hash}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.head(url, auth=(user, password))
        except httpx.HTTPError:
            return ConnectorResult(status="UNKNOWN")
        if resp.status_code == 200:
            return ConnectorResult(
                status="SUCCEEDED",
                normalized_result={"outcome": "CONFIRMED_EXECUTED", "content_hash": content_hash},
            )
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"outcome": "CONFIRMED_NOT_EXECUTED", "content_hash": content_hash},
        )

    async def validate(self) -> ConnectorHealth:
        endpoint, _, user, password = self._minio()
        try:
            httpx.get(f"{endpoint}/minio/health/live", timeout=3.0)
            httpx.put(
                f"{endpoint}/olympus-artifacts/.keep",
                content=b"",
                auth=(user, password),
                timeout=3.0,
            )
        except httpx.HTTPError:
            return ConnectorHealth(ok=False, message="MinIO unreachable")
        return ConnectorHealth(ok=True, message="artifact_s3 ready")


class IssueTrackerGiteaConnector:
    name = "issue_tracker_gitea"
    actions = {"post_comment", "close", "update_status", "link_release"}

    def _api(self, action: ConnectorAction) -> tuple[str, dict[str, str]]:
        base = str(
            action.policy_context.get("gitea_url")
            or os.environ.get("OLYMPUS_GITEA_URL", "http://127.0.0.1:3000")
        ).rstrip("/")
        cred = action.inputs.get("_credential")
        token = ""
        if isinstance(cred, ResolvedCredential):
            token = cred.secret.get_secret_value()
        headers = {"Authorization": f"token {token}"} if token else {}
        return f"{base}/api/v1", headers

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        api, headers = self._api(action)
        owner = str(action.inputs["owner"])
        repo = str(action.inputs["repo"])
        issue_number = int(action.inputs["issue_number"])
        idem = action.idempotency_key
        if action.action == "post_comment":
            body = str(action.inputs.get("body", "")) + f"\n\n{_idem_marker(idem)}"
            fault = action.inputs.get("_fault_mode")
            url = f"{api}/repos/{owner}/{repo}/issues/{issue_number}/comments"
            req_headers = dict(headers)
            if fault:
                proxy = os.environ.get("OLYMPUS_FAULT_PROXY_URL", "http://127.0.0.1:9099")
                req_headers["X-Olympus-Target"] = api.split("/api/v1")[0]
                req_headers["X-Olympus-Fault"] = str(fault)
                url = f"{proxy}/api/v1/repos/{owner}/{repo}/issues/{issue_number}/comments"
            try:
                with httpx.Client(timeout=30.0) as client:
                    listed = client.get(
                        f"{api}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                        headers=headers,
                    )
                    if listed.status_code == 200:
                        for c in listed.json():
                            if _idem_marker(idem) in str(c.get("body", "")):
                                return ConnectorResult(
                                    status="SUCCEEDED",
                                    normalized_result={"comment_id": c["id"]},
                                    external_ref=str(c["id"]),
                                )
                    resp = client.post(url, json={"body": body}, headers=req_headers)
            except httpx.HTTPError:
                return ConnectorResult(status="UNKNOWN", error_class="ISSUE_NETWORK")
            if resp.status_code == 504 and fault:
                return ConnectorResult(status="UNKNOWN", error_class="ISSUE_TIMEOUT")
            if resp.status_code >= 400:
                return ConnectorResult(
                    status="FAILED_FINAL",
                    error_class="ISSUE_4XX",
                    error_detail=str(resp.status_code),
                )
            data = resp.json()
            return ConnectorResult(
                status="SUCCEEDED",
                normalized_result={"comment_id": data.get("id")},
                external_ref=str(data.get("id")),
            )
        if action.action in {"close", "update_status"}:
            state = (
                "closed" if action.action == "close" else str(action.inputs.get("state", "open"))
            )
            fault = action.inputs.get("_fault_mode")
            url = f"{api}/repos/{owner}/{repo}/issues/{issue_number}"
            req_headers = dict(headers)
            if fault:
                proxy = os.environ.get("OLYMPUS_FAULT_PROXY_URL", "http://127.0.0.1:9099")
                req_headers["X-Olympus-Target"] = api.split("/api/v1")[0]
                req_headers["X-Olympus-Fault"] = str(fault)
                url = f"{proxy}/api/v1/repos/{owner}/{repo}/issues/{issue_number}"
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.patch(url, json={"state": state}, headers=req_headers)
            except httpx.HTTPError:
                return ConnectorResult(status="UNKNOWN", error_class="ISSUE_NETWORK")
            if resp.status_code == 504 and fault:
                return ConnectorResult(status="UNKNOWN", error_class="ISSUE_TIMEOUT")
            if resp.status_code >= 400:
                return ConnectorResult(status="FAILED_FINAL", error_class="ISSUE_4XX")
            return ConnectorResult(status="SUCCEEDED", normalized_result={"state": state})
        if action.action == "link_release":
            release_url = str(action.inputs.get("release_url", ""))
            return await self.execute(
                ConnectorAction(
                    connector=self.name,
                    action="post_comment",
                    target_resource=action.target_resource,
                    inputs={
                        **action.inputs,
                        "body": f"Release: {release_url}",
                    },
                    idempotency_key=idem,
                    correlation_id=action.correlation_id,
                    expected_result_schema=action.expected_result_schema,
                    policy_context=action.policy_context,
                )
            )
        return ConnectorResult(status="FAILED_FINAL", error_class="UNKNOWN_ACTION")

    async def reconcile(self, request: ReconciliationRequest) -> ConnectorResult:
        marker = _idem_marker(request.idempotency_key)
        owner = str(request.expected.get("owner", ""))
        repo = str(request.expected.get("repo", ""))
        issue_number = int(request.expected.get("issue_number", 0))
        api_base = str(
            request.expected.get("api_base") or os.environ.get("OLYMPUS_GITEA_URL", "")
        ).rstrip("/")
        if not api_base or not owner:
            return ConnectorResult(status="UNKNOWN", error_class="MISSING_EXPECTED")
        api = f"{api_base}/api/v1"
        token = str(request.expected.get("token", ""))
        headers = {"Authorization": f"token {token}"} if token else {}
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    f"{api}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                    headers=headers,
                )
        except httpx.HTTPError:
            return ConnectorResult(status="UNKNOWN")
        if resp.status_code != 200:
            return ConnectorResult(status="UNKNOWN")
        for c in resp.json():
            if marker in str(c.get("body", "")):
                return ConnectorResult(
                    status="SUCCEEDED",
                    normalized_result={
                        "outcome": "CONFIRMED_EXECUTED",
                        "comment_id": c["id"],
                    },
                )
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"outcome": "CONFIRMED_NOT_EXECUTED"},
        )

    async def validate(self) -> ConnectorHealth:
        return ConnectorHealth(ok=True, message="issue_tracker_gitea ready")


class DeployLocalConnector:
    name = "deployment_local"
    actions = {"deploy", "status", "rollback"}

    def _deploy_root(self) -> Path:
        root = Path(os.environ.get("OLYMPUS_DEPLOY_ROOT", "./.deployments"))
        root.mkdir(parents=True, exist_ok=True)
        return root

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        if action.action == "deploy":
            project_id = str(action.inputs["project_id"])
            release_id = str(action.inputs["release_id"])
            tag = str(action.inputs.get("tag", release_id))
            target = self._deploy_root() / project_id / release_id
            target.mkdir(parents=True, exist_ok=True)
            marker = target / "DEPLOYED"
            marker.write_text(json.dumps({"tag": tag, "status": "HEALTHY"}), encoding="utf-8")
            return ConnectorResult(
                status="SUCCEEDED",
                normalized_result={"path": str(target), "status": "HEALTHY"},
                external_ref=release_id,
            )
        if action.action == "status":
            project_id = str(action.inputs["project_id"])
            release_id = str(action.inputs["release_id"])
            marker = self._deploy_root() / project_id / release_id / "DEPLOYED"
            if not marker.is_file():
                return ConnectorResult(status="FAILED_FINAL", error_class="NOT_DEPLOYED")
            data = json.loads(marker.read_text(encoding="utf-8"))
            return ConnectorResult(status="SUCCEEDED", normalized_result=data)
        if action.action == "rollback":
            project_id = str(action.inputs["project_id"])
            to_release = str(action.inputs["to_release_id"])
            current = str(action.inputs["release_id"])
            cur_path = self._deploy_root() / project_id / current
            if cur_path.exists():
                shutil.rmtree(cur_path)
            return await self.execute(
                ConnectorAction(
                    connector=self.name,
                    action="deploy",
                    target_resource=action.target_resource,
                    inputs={
                        "project_id": project_id,
                        "release_id": to_release,
                        "tag": to_release,
                    },
                    idempotency_key=action.idempotency_key,
                    correlation_id=action.correlation_id,
                    expected_result_schema=action.expected_result_schema,
                )
            )
        return ConnectorResult(status="FAILED_FINAL", error_class="UNKNOWN_ACTION")

    async def reconcile(self, request: ReconciliationRequest) -> ConnectorResult:
        project_id = str(request.expected.get("project_id", ""))
        release_id = str(request.expected.get("release_id", ""))
        marker = self._deploy_root() / project_id / release_id / "DEPLOYED"
        if marker.is_file():
            return ConnectorResult(
                status="SUCCEEDED",
                normalized_result={"outcome": "CONFIRMED_EXECUTED", "status": "HEALTHY"},
            )
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"outcome": "CONFIRMED_NOT_EXECUTED"},
        )

    async def validate(self) -> ConnectorHealth:
        self._deploy_root()
        return ConnectorHealth(ok=True, message="deployment_local ready")


class HttpGenericConnector:
    name = "http_generic"
    actions = {"request"}

    def _allowed_hosts(self) -> set[str]:
        policy = load_policy_file().get("outbound", {}).get("http_generic", {})
        hosts = policy.get("allowed_hosts", [])
        return {str(h).lower() for h in hosts}

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        if action.action != "request":
            return ConnectorResult(status="FAILED_FINAL", error_class="UNKNOWN_ACTION")
        url = str(action.inputs["url"])
        method = str(action.inputs.get("method", "GET")).upper()
        from urllib.parse import urlparse

        host = urlparse(url).hostname or ""
        if host.lower() not in self._allowed_hosts():
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="HOST_DENIED",
                error_detail=host,
            )
        allow_unreconcilable = bool(
            load_policy_file()
            .get("outbound", {})
            .get("http_generic", {})
            .get("allow_unreconcilable")
        )
        if (
            method not in {"GET", "HEAD"}
            and not allow_unreconcilable
            and not action.inputs.get("_reconcile_expected")
        ):
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="UNRECONCILABLE_MUTATION",
            )
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.request(
                    method,
                    url,
                    content=action.inputs.get("body"),
                    headers=action.inputs.get("headers") or {},
                )
        except httpx.HTTPError:
            return ConnectorResult(status="UNKNOWN", error_class="HTTP_NETWORK")
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"status_code": resp.status_code, "body": resp.text[:2000]},
        )

    async def reconcile(self, request: ReconciliationRequest) -> ConnectorResult:
        del request
        return ConnectorResult(status="UNKNOWN", error_class="NO_RECONCILE")

    async def validate(self) -> ConnectorHealth:
        return ConnectorHealth(ok=True, message="http_generic ready")


def register_outbound_connectors(registry: Any) -> None:
    for conn in (
        HttpCiConnector(),
        GithubActionsCiConnector(),
        ArtifactFsConnector(),
        ArtifactS3Connector(),
        IssueTrackerGiteaConnector(),
        DeployLocalConnector(),
        HttpGenericConnector(),
    ):
        registry.register(conn)
