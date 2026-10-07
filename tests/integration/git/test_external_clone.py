import subprocess
from pathlib import Path

import pytest
from core.commands.context import CommandContext
from core.domain.enums import RepositoryProvider, RepositoryStatus
from core.domain.projects.models import Project
from core.repositories.materialization import RepositoryMaterializationService
from core.repositories.service import RepositoryService


@pytest.mark.git
async def test_external_clone_file_origin(
    db_session,
    system_ctx: CommandContext,
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    (origin / "README.md").write_text("origin\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "trunk"], cwd=origin, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=origin,
        check=True,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=origin, check=True, capture_output=True, text=True
    ).stdout.strip()
    project = Project(key="PRJ-0002", name="brownfield")
    db_session.add(project)
    await db_session.flush()
    svc = RepositoryService()
    repo = await svc.register_external(
        db_session,
        project.id,
        "ext",
        RepositoryProvider.LOCAL,
        f"file://{origin.resolve()}",
        "",
        "none:",
        system_ctx,
    )
    mat = RepositoryMaterializationService()
    await mat.materialize_external(db_session, repo.id, system_ctx)
    await db_session.refresh(repo)
    assert repo.status == RepositoryStatus.READY
    assert repo.default_branch == "trunk"
    assert repo.registered_sha == head
