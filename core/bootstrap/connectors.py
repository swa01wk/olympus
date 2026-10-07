"""Register built-in connectors (idempotent)."""

from __future__ import annotations

from core.integrations.connectors.git_local import register_git_local
from core.integrations.connectors.git_provider.connector import register_git_providers
from core.integrations.connectors.outbound import register_outbound_connectors
from core.integrations.connectors.registry import get_connector_registry


def ensure_connectors_registered() -> None:
    registry = get_connector_registry()
    if "git_local" not in registry.list_connectors():
        register_git_local(registry)
    if "git_provider_gitea" not in registry.list_connectors():
        register_git_providers(registry)
    if "ci_http" not in registry.list_connectors():
        register_outbound_connectors(registry)
