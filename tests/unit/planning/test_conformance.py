import pytest
from core.planning.implementation_specs.conformance import ArchitectureConformanceValidator
from core.planning.models import ArchitectureContract
from core.planning.schemas import ImplementationSpecBody
from tests.fixtures.planning_harness import (
    create_ticket_implementation_spec,
    supportdesk_architecture_proposal,
)

pytestmark = pytest.mark.unit


def test_conformance_passes_for_valid_draft() -> None:
    proposal = supportdesk_architecture_proposal()
    draft = create_ticket_implementation_spec().body
    contracts = [
        ArchitectureContract(
            architecture_id=__import__("uuid").uuid4(),
            key=c.key,
            kind=c.kind,
            name=c.name,
            definition={
                "method": c.method,
                "path": c.path,
                "description": c.description,
            },
        )
        for c in proposal.contracts
    ]
    report = ArchitectureConformanceValidator().validate(draft, proposal.body, contracts)
    assert report.ok


def test_conformance_accepts_recursive_py_file_scope() -> None:
    proposal = supportdesk_architecture_proposal()
    draft = create_ticket_implementation_spec().body.model_copy(
        update={"file_scope": ["app/api/**/*.py", "tests/**/*.py"]}
    )
    report = ArchitectureConformanceValidator().validate(draft, proposal.body, [])
    assert "invalid file_scope pattern" not in " ".join(report.violations)


def test_conformance_rejects_unknown_component() -> None:
    proposal = supportdesk_architecture_proposal()
    draft = ImplementationSpecBody(
        summary="bad",
        components=["unknown"],
        file_scope=["app/api/**"],
    )
    report = ArchitectureConformanceValidator().validate(draft, proposal.body, [])
    assert not report.ok
