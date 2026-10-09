"""Authored characterization test code stored as artifacts and materialized for runs."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path, PurePosixPath

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.artifacts.models import Artifact
from core.execution.artifacts import ArtifactStore
from core.intelligence.baselines.enums import BaselineCheckKind
from core.intelligence.baselines.models import BehavioralBaseline

AUTHORED_TEST_DIR = "tests/olympus_characterization"
ARTIFACT_KIND = "CHARACTERIZATION_TEST"


def authored_test_path(lineage_key: str, requested: str | None) -> str:
    """Repo-relative path for an authored test, always inside ``AUTHORED_TEST_DIR``."""
    stem = PurePosixPath(requested or "").stem
    stem = re.sub(r"[^A-Za-z0-9_]", "_", stem).strip("_")
    if not stem.startswith("test_"):
        stem = f"test_{stem}" if stem else "test_characterization"
    key = re.sub(r"[^A-Za-z0-9]", "_", lineage_key).lower()
    return f"{AUTHORED_TEST_DIR}/{stem}_{key}.py"


async def store_authored_test(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    delivery_cycle_id: uuid.UUID,
    execution_id: uuid.UUID | None,
    test_path: str,
    test_code: str,
) -> Artifact:
    return await ArtifactStore().put(
        session,
        project_id=project_id,
        delivery_cycle_id=delivery_cycle_id,
        execution_id=execution_id,
        kind=ARTIFACT_KIND,
        schema_name="CharacterizationTest",
        schema_version="1",
        content={"test_path": test_path, "test_code": test_code},
    )


async def load_authored_test(
    session: AsyncSession, baseline: BehavioralBaseline
) -> tuple[str, str] | None:
    """``(test_path, test_code)`` for an AUTHORED_TEST baseline, if its code is stored."""
    if baseline.check_kind != BaselineCheckKind.AUTHORED_TEST or baseline.check_artifact_id is None:
        return None
    artifact = await session.get(Artifact, baseline.check_artifact_id)
    if artifact is None:
        return None
    content = artifact.inline
    if content is None:
        content = json.loads(ArtifactStore().read_bytes(artifact))
    path = str(content.get("test_path") or baseline.check_ref)
    code = content.get("test_code")
    if not isinstance(code, str) or not code.strip():
        return None
    return path, code


def materialize(root: Path, test_path: str, test_code: str) -> Path:
    target = root / test_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(test_code, encoding="utf-8")
    return target
