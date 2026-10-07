from __future__ import annotations

from core.intelligence.impact.enums import ImpactKind
from core.intelligence.impact.models import ImpactItem
from core.planning.implementation_specs.delta import ImplementationSpecDeltaService
from core.planning.schemas import ApiDef, ImplementationSpecBody


def _item(ref: str, path: str) -> ImpactItem:
    return ImpactItem(
        impact_assessment_id=None,  # type: ignore[arg-type]
        item_type="CODE_ENTITY",
        ref=ref,
        impact_kind=ImpactKind.DIRECT.value,
        contract_surface=True,
        path=[path],
        confidence=1.0,
        retrieval_source="STRUCTURAL",
        selected_for_verification=True,
        rationale="test",
    )


def test_unaddressed_direct_surface_rejected() -> None:
    body = ImplementationSpecBody(
        summary="delta",
        components=["api"],
        apis=[ApiDef(method="POST", path="/health", contract_key="HC")],
        file_scope=["src/api/**"],
    )
    ok, errors = ImplementationSpecDeltaService().validate_impact_consistency(
        body,
        impact_items=[_item("ROUTE:POST /tickets", "src/api/tickets.py")],
    )
    assert not ok
    assert errors


def test_file_scope_covers_impact_path() -> None:
    body = ImplementationSpecBody(
        summary="delta",
        components=["tickets"],
        apis=[ApiDef(method="POST", path="/tickets", contract_key="T")],
        file_scope=["src/api/tickets.py"],
    )
    ok, errors = ImplementationSpecDeltaService().validate_impact_consistency(
        body,
        impact_items=[_item("ROUTE:POST /tickets", "src/api/tickets.py")],
    )
    assert ok, errors
