"""Git provider connector (GitHub / Gitea) — fetch, push, clone, PR helpers."""

from __future__ import annotations

from typing import Any

import httpx
from core.integrations.connectors.base import (
    ConnectorAction,
    ConnectorHealth,
    ConnectorResult,
    ReconciliationRequest,
)
from core.integrations.connectors.git_provider import _git_ops
from core.repositories.credentials import ResolvedCredential
from core.repositories.workspace_locator import WorkspaceLocator


class GitProviderConnector:
    def __init__(
        self,
        name: str,
        provider: str,
        locator: WorkspaceLocator | None = None,
    ) -> None:
        self.name = name
        self.provider = provider
        self._locator = locator or WorkspaceLocator()
        self.actions = {
            "fetch",
            "push_branch",
            "push_release",
            "clone",
            "create_pull_request",
            "read_merge_status",
            "ensure_webhook",
            "validate_registration",
        }

    def _credential(self, action: ConnectorAction) -> ResolvedCredential | None:
        cred = action.inputs.get("_credential")
        if isinstance(cred, ResolvedCredential):
            return cred
        return None

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        if action.action == "push_release" and not action.policy_context.get("release_executor"):
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="POLICY_DENIED",
                error_detail="push_release requires release executor identity",
            )
        cred = self._credential(action)
        handler = {
            "fetch": lambda: _git_ops.action_fetch(self._locator, action, cred),
            "push_branch": lambda: _git_ops.action_push_branch(self._locator, action, cred),
            "push_release": lambda: _git_ops.action_push_release(self._locator, action, cred),
            "clone": lambda: _git_ops.action_clone(self._locator, action, cred),
            "create_pull_request": lambda: self._create_pr(action, cred),
            "read_merge_status": lambda: self._read_merge_status(action, cred),
            "ensure_webhook": lambda: self._ensure_webhook(action, cred),
            "validate_registration": lambda: self._validate_registration(action, cred),
        }.get(action.action)
        if handler is None:
            return ConnectorResult(
                status="FAILED_FINAL",
                error_class="UNKNOWN_ACTION",
                error_detail=action.action,
            )
        return handler()

    async def reconcile(self, request: ReconciliationRequest) -> ConnectorResult:
        expected = request.expected or {}
        logical = str(expected.get("logical_location", ""))
        ref = str(expected.get("ref", ""))
        sha = str(expected.get("sha", ""))
        if not logical or not ref or not sha:
            return ConnectorResult(status="UNKNOWN", error_class="MISSING_EXPECTED")
        return _git_ops.reconcile_ref_sha(self._locator, logical, ref, sha)

    async def validate(self) -> ConnectorHealth:
        return ConnectorHealth(ok=True, message=f"{self.name} ready")

    def _api_base(self, action: ConnectorAction) -> str:
        base = action.inputs.get("api_base_url") or action.policy_context.get("base_url")
        if not base:
            if self.provider == "GITEA":
                return "http://localhost:3000/api/v1"
            return "https://api.github.com"
        return str(base).rstrip("/")

    def _create_pr(
        self, action: ConnectorAction, cred: ResolvedCredential | None
    ) -> ConnectorResult:
        if cred is None:
            return ConnectorResult(status="FAILED_FINAL", error_class="AUTH", error_detail="token")
        owner = str(action.inputs["owner"])
        repo = str(action.inputs["repo"])
        head = str(action.inputs["head"])
        base = str(action.inputs.get("base", "main"))
        title = str(action.inputs.get("title", "Olympus integration"))
        idem = action.idempotency_key
        body = str(action.inputs.get("body", "")) + f"\n\n<!-- olympus:idem={idem} -->"
        token = cred.secret.get_secret_value()
        api = self._api_base(action)
        headers = {"Authorization": f"token {token}"}
        if self.provider == "GITHUB":
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        try:
            with httpx.Client(timeout=30.0) as client:
                search = client.get(
                    f"{api}/repos/{owner}/{repo}/pulls",
                    params={"head": f"{owner}:{head}", "state": "all"},
                    headers=headers,
                )
                if search.status_code == 200:
                    for pr in search.json():
                        if pr.get("head", {}).get("ref") == head:
                            return ConnectorResult(
                                status="SUCCEEDED",
                                normalized_result={"number": pr["number"], "url": pr["html_url"]},
                                external_ref=str(pr["number"]),
                            )
                resp = client.post(
                    f"{api}/repos/{owner}/{repo}/pulls",
                    json={"title": title, "head": head, "base": base, "body": body},
                    headers=headers,
                )
        except httpx.TimeoutException:
            return ConnectorResult(status="UNKNOWN", error_class="TIMEOUT")
        except httpx.RequestError as exc:
            return ConnectorResult(
                status="FAILED_RETRYABLE", error_class="NETWORK", error_detail=str(exc)
            )
        if resp.status_code in {401, 403}:
            return ConnectorResult(
                status="FAILED_FINAL", error_class="AUTH", error_detail=resp.text[:200]
            )
        if resp.status_code >= 500:
            return ConnectorResult(status="FAILED_RETRYABLE", error_class="HTTP_5XX")
        if resp.status_code >= 400:
            return ConnectorResult(
                status="FAILED_FINAL", error_class="HTTP_4XX", error_detail=resp.text[:200]
            )
        data = resp.json()
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"number": data.get("number"), "url": data.get("html_url")},
            external_ref=str(data.get("number", "")),
        )

    def _read_merge_status(
        self, action: ConnectorAction, cred: ResolvedCredential | None
    ) -> ConnectorResult:
        if cred is None:
            return ConnectorResult(status="FAILED_FINAL", error_class="AUTH")
        owner = str(action.inputs["owner"])
        repo = str(action.inputs["repo"])
        number = int(action.inputs["number"])
        token = cred.secret.get_secret_value()
        api = self._api_base(action)
        headers = {"Authorization": f"token {token}"}
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(
                    f"{api}/repos/{owner}/{repo}/pulls/{number}",
                    headers=headers,
                )
        except httpx.TimeoutException:
            return ConnectorResult(status="UNKNOWN", error_class="TIMEOUT")
        if resp.status_code != 200:
            return ConnectorResult(
                status="FAILED_FINAL", error_class="HTTP", error_detail=str(resp.status_code)
            )
        data = resp.json()
        return ConnectorResult(
            status="SUCCEEDED",
            normalized_result={"merged": data.get("merged"), "state": data.get("state")},
        )

    def _ensure_webhook(
        self, action: ConnectorAction, cred: ResolvedCredential | None
    ) -> ConnectorResult:
        return ConnectorResult(status="SUCCEEDED", normalized_result={"registered": True})

    def _validate_registration(
        self, action: ConnectorAction, cred: ResolvedCredential | None
    ) -> ConnectorResult:
        remote_url = str(action.inputs.get("remote_url", ""))
        if remote_url.startswith("https://"):
            return ConnectorResult(status="SUCCEEDED", normalized_result={"ok": True})
        if self.provider == "GITEA" and remote_url.startswith(
            ("http://127.0.0.1", "http://localhost")
        ):
            return ConnectorResult(status="SUCCEEDED", normalized_result={"ok": True})
        return ConnectorResult(
            status="FAILED_FINAL",
            error_class="INVALID_URL",
            error_detail="HTTPS remote_url required",
        )


def register_git_providers(registry: Any) -> None:
    registry.register(GitProviderConnector("git_provider_github", "GITHUB"))
    registry.register(GitProviderConnector("git_provider_gitea", "GITEA"))
