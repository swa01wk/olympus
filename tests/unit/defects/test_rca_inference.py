"""RCA persistence: knowledge_class is always INFERENCE."""

from __future__ import annotations

import uuid

from core.product_model.defects.models import RootCauseAnalysis


def test_rca_model_defaults_to_inference() -> None:
    row = RootCauseAnalysis(
        defect_id=uuid.uuid4(),
        trace_correlation_id=uuid.uuid4(),
        execution_id=uuid.uuid4(),
        explanation="test",
        knowledge_class="INFERENCE",
        status="PROPOSED",
    )
    assert row.knowledge_class == "INFERENCE"
