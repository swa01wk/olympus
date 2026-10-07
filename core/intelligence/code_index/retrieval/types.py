from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from core.intelligence.code_index.enums import EntityType

RetrievalSource = Literal["STRUCTURAL", "LEXICAL", "SEMANTIC"]


class RetrievalHit(BaseModel):
    entity_id: uuid.UUID
    stable_key: str
    type: EntityType
    retrieval_source: RetrievalSource
    score: float
    path: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    index_version_id: uuid.UUID
    commit_sha: str
    qualified_name: str = ""
    file_path: str | None = None
