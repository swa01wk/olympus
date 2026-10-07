"""Maps logical workspace locations to confined paths under OLYMPUS_WORKSPACE_ROOT."""

from __future__ import annotations

import uuid
from pathlib import Path

from core.config.settings import OlympusSettings, get_settings


class WorkspaceLocator:
    """Maps logical workspace locations to confined physical paths under configured roots."""

    def __init__(self, settings: OlympusSettings | None = None) -> None:
        self._settings_override = settings

    def _settings(self) -> OlympusSettings:
        if self._settings_override is not None:
            return self._settings_override
        return get_settings()

    def canonical_location(self, project_id: uuid.UUID) -> str:
        return f"projects/{project_id}/repo"

    def execution_location(self, project_id: uuid.UUID, execution_key: str) -> str:
        return f"projects/{project_id}/worktrees/{execution_key}"

    def resolve(self, backend: str, logical_location: str) -> Path:
        if backend != "LOCAL_FILESYSTEM":
            raise ValueError(f"Unsupported storage backend: {backend}")
        if logical_location.startswith("/") or ".." in logical_location.split("/"):
            raise ValueError("Invalid logical location")
        if len(logical_location) >= 2 and logical_location[1] == ":":
            raise ValueError("Invalid logical location")
        settings = self._settings()
        root = settings.olympus_workspace_root
        if logical_location.startswith("projects/") and "/worktrees/" in logical_location:
            root = settings.effective_worktree_root
        candidate = (root / logical_location).resolve()
        root_resolved = root.resolve()
        if (
            root_resolved not in candidate.parents
            and candidate != root_resolved
            and not str(candidate).startswith(str(root_resolved) + "/")
        ):
            raise ValueError("Logical location escapes workspace root")
        return candidate
