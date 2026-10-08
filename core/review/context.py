from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RevisionContext:
    approval_id: uuid.UUID
    feedback: str
    previous_output_json: str
    subject_type: str
    subject_id: uuid.UUID
