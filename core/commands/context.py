from __future__ import annotations

import uuid
from dataclasses import dataclass

from core.domain.actors.models import Actor


@dataclass(frozen=True)
class CommandContext:
    actor: Actor
    correlation_id: str
    idempotency_key: str | None = None
    command_log_id: uuid.UUID | None = None
