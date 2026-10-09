from __future__ import annotations

import os
import time
import uuid

import pytest
from core.config.settings import get_settings
from core.execution.worktrees.sweeper import WorktreeSweeper


@pytest.mark.git
async def test_sweeper_keeps_fresh_unregistered_worktree(db_session) -> None:
    # An in-flight execution's workspace row is uncommitted, so the sweeper sees
    # only the directory; it must not delete it until the grace period passes.
    root = get_settings().effective_worktree_root
    wt = root / "projects" / str(uuid.uuid4()) / "worktrees" / "EX-0001"
    wt.mkdir(parents=True)
    (wt / "tests").mkdir()

    await WorktreeSweeper().cleanup_orphans(db_session)
    assert wt.is_dir()

    stale = time.time() - get_settings().worktree_orphan_grace_seconds - 60
    os.utime(wt, (stale, stale))
    await WorktreeSweeper().cleanup_orphans(db_session)
    assert not wt.exists()
