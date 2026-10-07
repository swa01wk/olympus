"""Defect triage validation."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.product_model.defects.schemas import DefectTriage
from core.product_model.models import Feature

_VALID_SIGNATURE_KINDS = frozenset({"http_status", "exception_type", "message_regex"})


def normalize_defect_triage_signature(
    triage: DefectTriage, defect_description: str
) -> DefectTriage:
    """Fill observed_symptom_signature when the model omitted it but text implies HTTP 5xx."""
    sig = triage.observed_symptom_signature or {}
    if sig.get("kind") in _VALID_SIGNATURE_KINDS:
        return triage
    blob = " ".join(
        [
            defect_description,
            triage.reproduction_plan.observed_symptom,
            " ".join(s.description for s in triage.reproduction_plan.steps),
        ]
    ).lower()
    if "500" in blob or "internal server error" in blob:
        return triage.model_copy(
            update={"observed_symptom_signature": {"kind": "http_status", "value": 500}}
        )
    if "409" in blob or "conflict" in blob:
        return triage.model_copy(
            update={"observed_symptom_signature": {"kind": "http_status", "value": 409}}
        )
    return triage


class DefectTriageValidator:
    async def validate(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        triage: DefectTriage,
        candidate_feature_keys: set[str],
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        for key in triage.feature_keys:
            if key not in candidate_feature_keys:
                feat = (
                    await session.execute(
                        select(Feature).where(Feature.project_id == project_id, Feature.key == key)
                    )
                ).scalar_one_or_none()
                if feat is None:
                    errors.append(f"feature_key_not_in_candidates:{key}")
        if len(triage.reproduction_plan.steps) < 1:
            errors.append("reproduction_plan_requires_step")
        if triage.severity not in {"S1", "S2", "S3", "S4"}:
            errors.append("invalid_severity")
        sig = triage.observed_symptom_signature.get("kind")
        if sig not in {"http_status", "exception_type", "message_regex"}:
            errors.append("invalid_symptom_signature")
        for key in triage.feature_keys:
            feat = (
                await session.execute(
                    select(Feature).where(Feature.project_id == project_id, Feature.key == key)
                )
            ).scalar_one_or_none()
            if feat is None:
                errors.append(f"feature_not_found:{key}")
        return not errors, errors
