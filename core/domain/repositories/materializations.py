from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, UUIDPkMixin
from core.domain.enums import MaterializationAttemptStatus, MaterializationKind
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column


class RepositoryMaterialization(Base, UUIDPkMixin):
    __tablename__ = "repository_materializations"

    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repositories.id"), index=True)
    kind: Mapped[MaterializationKind]
    attempt: Mapped[int] = mapped_column(Integer)
    status: Mapped[MaterializationAttemptStatus]
    action_request_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list
    )
    resulting_sha: Mapped[str | None] = mapped_column(String(64), default=None)
    observed_default_branch: Mapped[str | None] = mapped_column(String(256), default=None)
    error_class: Mapped[str | None] = mapped_column(String(64), default=None)
    error_detail: Mapped[str | None] = mapped_column(String(2048), default=None)
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
