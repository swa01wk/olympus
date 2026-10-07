from __future__ import annotations

from pathlib import Path

import pytest
from core.domain.enums import EvidenceRequirement
from core.product_model.schemas import (
    AcceptanceCriterionDraft,
    CapabilityDraft,
    FeatureDraft,
    FeatureSpecBody,
    FeatureSpecDraft,
    ProductDecomposition,
    RequirementDraft,
)
from core.product_model.source_chunking import (
    chunk_markdown_by_headings,
    merge_product_decompositions,
)


@pytest.mark.unit
def test_chunk_markdown_leaves_small_documents_intact() -> None:
    text = "# One\n\nbody\n"
    assert chunk_markdown_by_headings(text, 10_000) == [text]


@pytest.mark.unit
def test_chunk_markdown_splits_on_headings_under_budget() -> None:
    prd = Path(__file__).resolve().parents[2] / "fixtures" / "supportdesk" / "PRD_large.md"
    text = prd.read_text()
    chunks = chunk_markdown_by_headings(text, 400)
    assert len(chunks) >= 3
    assert all(len(c) <= 400 for c in chunks)
    assert "Create Ticket" in chunks[0] or any("Create Ticket" in c for c in chunks)


def _single_cap_decomposition(cap_ref: str, feat_ref: str, section: str) -> ProductDecomposition:
    return ProductDecomposition(
        capabilities=[
            CapabilityDraft(ref=cap_ref, name=cap_ref, description="d", source_sections=[section])
        ],
        features=[
            FeatureDraft(
                ref=feat_ref,
                capability_ref=cap_ref,
                name=feat_ref,
                description="d",
                source_sections=[section],
            )
        ],
        feature_specs=[
            FeatureSpecDraft(
                ref=f"SPEC-{feat_ref}",
                feature_ref=feat_ref,
                body=FeatureSpecBody(
                    behavior="b",
                    summary="s",
                    inputs=["i"],
                    outputs=["o"],
                    rules=["r"],
                ),
            )
        ],
        requirements=[
            RequirementDraft(
                ref=f"REQ-{feat_ref}",
                feature_spec_ref=f"SPEC-{feat_ref}",
                statement="must",
                kind="FUNCTIONAL",
                priority="MUST",
            )
        ],
        user_stories=[],
        acceptance_criteria=[
            AcceptanceCriterionDraft(
                ref=f"AC-{feat_ref}",
                feature_spec_ref=f"SPEC-{feat_ref}",
                statement="ac",
                given=None,
                when=None,
                then=None,
                mandatory=True,
                evidence_requirement=EvidenceRequirement.EXECUTABLE,
                requirement_refs=[f"REQ-{feat_ref}"],
            )
        ],
        open_questions=[],
    )


@pytest.mark.unit
def test_merge_product_decompositions_unions_distinct_refs() -> None:
    left = _single_cap_decomposition("CAP-1", "FEAT-1", "A")
    right = _single_cap_decomposition("CAP-2", "FEAT-2", "B")
    merged = merge_product_decompositions(left, right)
    assert {c.ref for c in merged.capabilities} == {"CAP-1", "CAP-2"}
    assert {f.ref for f in merged.features} == {"FEAT-1", "FEAT-2"}
    dup = merge_product_decompositions(merged, left)
    assert len(dup.capabilities) == 2
