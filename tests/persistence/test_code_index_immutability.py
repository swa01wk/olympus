import pytest
from core.intelligence.code_index.enums import IndexKind, IndexSource, IndexVersionStatus
from core.intelligence.code_index.indexer import CodeIndexer
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.persistence


@pytest.mark.asyncio
async def test_ready_code_index_version_immutable(db_session, system_ctx) -> None:
    from tests.fixtures.code_index_harness import materialize_supportdesk_r1

    repo, sha = await materialize_supportdesk_r1(db_session, system_ctx)
    version = await CodeIndexer().build(
        db_session, repo.id, sha, IndexKind.CANDIDATE, IndexSource.REPOSITORY_SNAPSHOT, system_ctx
    )
    assert version.status == IndexVersionStatus.READY
    version.content_hash = "tampered"
    with pytest.raises(DBAPIError):
        await db_session.flush()
