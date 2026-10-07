"""Deterministic validation for Kira change interpretation output."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.product_model.changes.schemas import ChangeInterpretation
from core.product_model.models import AcceptanceCriterion, Feature


class ChangeInterpretationValidator:
    def validate(
        self,
        interpretation: ChangeInterpretation,
        *,
        candidate_feature_keys: set[str],
        current_ac_lineage_keys: set[str],
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if interpretation.resolution == "EXISTING_FEATURE":
            if not interpretation.feature_key:
                errors.append("feature_key required for EXISTING_FEATURE")
            elif interpretation.feature_key not in candidate_feature_keys:
                errors.append(f"feature_key not in candidates: {interpretation.feature_key}")
        for change in interpretation.acceptance_criteria_changes:
            if change.op in {"MODIFY", "REMOVE"}:
                if not change.lineage_key:
                    errors.append(f"{change.op} AC requires lineage_key")
                elif change.lineage_key not in current_ac_lineage_keys:
                    errors.append(f"unknown AC lineage_key: {change.lineage_key}")
            if change.op == "ADD":
                if change.mandatory is None:
                    errors.append("ADD AC requires mandatory flag")
                if change.mandatory and change.evidence_requirement is None:
                    errors.append("mandatory ADD AC requires evidence_requirement")
            if change.op == "REMOVE" and change.mandatory and not (change.rationale or "").strip():
                errors.append(f"REMOVE mandatory AC {change.lineage_key} requires rationale")
        return (not errors, errors)

    async def load_current_ac_keys(
        self,
        session: AsyncSession,
        spec_id: uuid.UUID,
    ) -> set[str]:
        rows = (
            await session.execute(
                select(AcceptanceCriterion.lineage_key).where(
                    AcceptanceCriterion.feature_spec_id == spec_id
                )
            )
        ).scalars()
        return set(rows)

    async def resolve_feature_id(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        feature_key: str,
    ) -> uuid.UUID | None:
        row = (
            await session.execute(
                select(Feature.id).where(
                    Feature.project_id == project_id,
                    Feature.key == feature_key,
                )
            )
        ).scalar_one_or_none()
        return row
