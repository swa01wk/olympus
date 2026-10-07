from __future__ import annotations

import pytest
from tests.fixtures.code_index_harness import materialize_supportdesk_r1


@pytest.fixture
async def supportdesk_repository(db_session, system_ctx):
    return await materialize_supportdesk_r1(db_session, system_ctx)
