from __future__ import annotations

import pytest
from core.intelligence.impact.models import Embedding

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_embedding_unique_per_subject_hash_model(db_session) -> None:
    vec = [0.0] * 1536
    row = Embedding(
        subject_type="CODE_ENTITY",
        subject_key="METHOD:test",
        content_hash="hash-a",
        model="text-embedding-3-small",
        dim=1536,
        vector=vec,
    )
    db_session.add(row)
    await db_session.flush()
    dupe = Embedding(
        subject_type="CODE_ENTITY",
        subject_key="METHOD:test",
        content_hash="hash-a",
        model="text-embedding-3-small",
        dim=1536,
        vector=vec,
    )
    db_session.add(dupe)
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.flush()
