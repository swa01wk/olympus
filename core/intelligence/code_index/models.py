from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, TimestampMixin, UUIDPkMixin
from core.intelligence.code_index.enums import (
    EntityType,
    IndexKind,
    IndexSource,
    IndexVersionStatus,
    RelationType,
)

INDEXER_VERSION = "p07.1"


class CodeIndexVersion(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "code_index_versions"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "commit_sha",
            "kind",
            "scope_ref",
            "indexer_version",
            name="uq_code_index_versions_repo_sha_kind_scope_ver",
        ),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True)
    commit_sha: Mapped[str] = mapped_column(String(64))
    kind: Mapped[IndexKind]
    source: Mapped[IndexSource]
    scope_ref: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[IndexVersionStatus]
    parent_index_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("code_index_versions.id"), default=None
    )
    indexer_version: Mapped[str] = mapped_column(String(32), default=INDEXER_VERSION)
    content_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class CodeEntity(Base, UUIDPkMixin):
    __tablename__ = "code_entities"
    __table_args__ = (
        UniqueConstraint("index_version_id", "stable_key", name="uq_code_entities_version_key"),
        Index(
            "ix_code_entities_qn_trgm",
            "qualified_name",
            postgresql_using="gin",
            postgresql_ops={"qualified_name": "gin_trgm_ops"},
        ),
        Index("ix_code_entities_file_path", "file_path"),
        Index("ix_code_entities_index_version_id", "index_version_id"),
    )

    index_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_index_versions.id", ondelete="CASCADE"),
        index=True,
    )
    stable_key: Mapped[str] = mapped_column(String(512))
    type: Mapped[EntityType]
    language: Mapped[str] = mapped_column(String(16), default="python")
    file_path: Mapped[str | None] = mapped_column(String(512), default=None)
    qualified_name: Mapped[str] = mapped_column(String(512))
    start_line: Mapped[int | None] = mapped_column(Integer, default=None)
    end_line: Mapped[int | None] = mapped_column(Integer, default=None)
    content_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    is_public: Mapped[bool] = mapped_column(default=True)
    entity_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class CodeRelation(Base, UUIDPkMixin):
    __tablename__ = "code_relations"
    __table_args__ = (
        UniqueConstraint(
            "index_version_id",
            "source_entity_id",
            "relation",
            "target_entity_id",
            name="uq_code_relations_version_src_rel_tgt",
        ),
        Index("ix_rel_src", "source_entity_id", "relation"),
        Index("ix_rel_tgt", "target_entity_id", "relation"),
    )

    index_version_id: Mapped[uuid.UUID] = mapped_column(index=True)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_entities.id", ondelete="CASCADE")
    )
    relation: Mapped[RelationType]
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_entities.id", ondelete="CASCADE")
    )
    provenance: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
