from __future__ import annotations

import os
import shutil

import pytest
from core.bootstrap.connectors import ensure_connectors_registered
from core.commands.context import CommandContext
from core.config.settings import clear_settings_cache
from core.domain.projects.models import Project
from core.execution.worktrees.manager import WorktreeManager
from core.integrations.connectors.registry import reset_connector_registry
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService
from core.repositories.workspace_locator import WorkspaceLocator
from tests.fixtures.gateway_harness import seed_gateway_execution


@pytest.mark.git
async def test_workspace_root_relocation(
    db_session,
    system_ctx: CommandContext,
    tmp_path,
) -> None:
    prior_workspace = os.environ.get("OLYMPUS_WORKSPACE_ROOT")
    prior_storage = os.environ.get("OLYMPUS_STORAGE_ROOT")
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    root_a.mkdir()
    try:
        os.environ["OLYMPUS_WORKSPACE_ROOT"] = str(root_a)
        clear_settings_cache()
        reset_connector_registry()
        ensure_connectors_registered()

        project = Project(key="reloc", name="Reloc")
        db_session.add(project)
        await db_session.flush()
        project_id = project.id
        repo = await RepositoryService().declare_managed(db_session, project_id, system_ctx)
        await RepositoryMaterializationService().provision_managed(db_session, repo.id, system_ctx)
        await db_session.refresh(repo)
        view = await RepositoryService().get_view(db_session, repo.id)
        assert view.workspace is not None
        logical = view.workspace.logical_location
        path_a = WorkspaceLocator().resolve("LOCAL_FILESYSTEM", logical)
        assert path_a.exists()

        root_b.mkdir(parents=True)
        shutil.move(str(root_a / "projects"), str(root_b / "projects"))
        os.environ["OLYMPUS_WORKSPACE_ROOT"] = str(root_b)
        clear_settings_cache()
        reset_connector_registry()
        ensure_connectors_registered()

        base = repo.canonical_commit
        assert base
        bundle = await seed_gateway_execution(
            db_session, repository=repo, base_commit=base, key_prefix="reloc"
        )
        ws = await WorktreeManager().create(
            db_session,
            bundle.execution,
            repo.id,
            base,
            actor_id=system_ctx.actor.id,
            correlation_id="reloc",
            project_id=project_id,
        )
        path_b = WorkspaceLocator().resolve("LOCAL_FILESYSTEM", ws.logical_location)
        assert path_b.exists()
    finally:
        if prior_workspace is not None:
            os.environ["OLYMPUS_WORKSPACE_ROOT"] = prior_workspace
        if prior_storage is not None:
            os.environ["OLYMPUS_STORAGE_ROOT"] = prior_storage
        clear_settings_cache()
        reset_connector_registry()
        ensure_connectors_registered()
