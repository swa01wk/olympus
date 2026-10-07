from __future__ import annotations

import pytest
from agents.atlas.schemas import ArchitectureProposal
from agents.kira.schemas import ImplementationSpecDraft, ProductDecomposition
from core.assurance.schemas import VerificationPlan, WardenReview
from core.runtime.structured_output import pydantic_to_json_schema


def _object_nodes_without_additional_properties_false(node: object) -> list[str]:
    missing: list[str] = []
    if not isinstance(node, dict):
        return missing
    if node.get("type") == "object" or "properties" in node:
        if node.get("additionalProperties") is not False:
            missing.append(node.get("title", "<object>"))
        for prop in (node.get("properties") or {}).values():
            missing.extend(_object_nodes_without_additional_properties_false(prop))
    if node.get("type") == "array":
        missing.extend(_object_nodes_without_additional_properties_false(node.get("items")))
    for key in ("anyOf", "oneOf", "allOf"):
        for variant in node.get(key) or []:
            missing.extend(_object_nodes_without_additional_properties_false(variant))
    for sub in (node.get("$defs") or {}).values():
        missing.extend(_object_nodes_without_additional_properties_false(sub))
    return missing


@pytest.mark.unit
def test_product_decomposition_schema_is_openai_strict_ready() -> None:
    schema = pydantic_to_json_schema(ProductDecomposition)
    missing = _object_nodes_without_additional_properties_false(schema)
    assert missing == []
    assert schema.get("additionalProperties") is False


@pytest.mark.unit
def test_architecture_proposal_schema_is_openai_strict_ready() -> None:
    schema = pydantic_to_json_schema(ArchitectureProposal)
    missing = _object_nodes_without_additional_properties_false(schema)
    assert missing == []
    assert schema.get("additionalProperties") is False


@pytest.mark.unit
def test_implementation_spec_draft_schema_is_openai_strict_ready() -> None:
    schema = pydantic_to_json_schema(ImplementationSpecDraft)
    missing = _object_nodes_without_additional_properties_false(schema)
    assert missing == []
    assert schema.get("additionalProperties") is False


@pytest.mark.unit
def test_warden_review_schema_is_openai_strict_ready() -> None:
    schema = pydantic_to_json_schema(WardenReview)
    missing = _object_nodes_without_additional_properties_false(schema)
    assert missing == []
    assert schema.get("additionalProperties") is False


@pytest.mark.unit
def test_verification_plan_schema_is_openai_strict_ready() -> None:
    schema = pydantic_to_json_schema(VerificationPlan)
    missing = _object_nodes_without_additional_properties_false(schema)
    assert missing == []
    assert schema.get("additionalProperties") is False
