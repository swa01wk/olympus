from __future__ import annotations

from agents.scout.schemas import (
    Citation,
    InferenceDraft,
    PrincipalEntityLink,
    RecoveredAcDraft,
    RecoveredFeatureDraft,
    RecoveredFeatureSpec,
    RepositorySurvey,
)
from core.intelligence.recovered_specs.validation import (
    RecoveryValidator,
    canonical_entity_keys,
    discovery_fact_aliases,
)
from core.planning.schemas import ArchitectureBody, TechnologyStack
from core.product_model.schemas import FeatureSpecBody


def _minimal_survey() -> RepositorySurvey:
    body = ArchitectureBody(
        summary="s",
        technology_stack=TechnologyStack(
            language="python", web="fastapi", orm="sqlalchemy", tests="pytest"
        ),
        components=[],
        layers=[],
        dependency_rules=[],
        directory_conventions=[],
        decisions=[],
        constraints=[],
        risks=[],
    )
    return RepositorySurvey(
        recovered_architecture=body,
        capabilities=[],
        features=[],
        inferences=[
            InferenceDraft(
                statement="inf",
                citations=[Citation(ref_type="OBSERVED_BEHAVIOR", ref="OB-0001")],
                confidence="LOW",
            )
        ],
        uncertainties=[],
    )


def test_discovery_entry_point_fact_alias_resolves() -> None:
    stmt = "Repository summary: entry_points = ['app/main.py:app']"
    statements = {stmt}
    aliases = discovery_fact_aliases(statements)
    assert "entry_points: app/main.py:app" in aliases
    survey = _minimal_survey()
    survey.inferences[0].citations = [
        Citation(ref_type="FACT", ref="entry_points: app/main.py:app"),
    ]
    ok, errors = RecoveryValidator().validate_survey(
        survey,
        behavior_ids=set(),
        fact_ids=aliases | statements,
        fact_statements=statements,
        entity_keys=set(),
    )
    assert ok, errors


def test_discovery_empty_config_files_fact_alias_resolves() -> None:
    stmt = "Repository summary: config_files = []"
    statements = {stmt}
    aliases = discovery_fact_aliases(statements)
    assert "config_files: []" in aliases
    survey = _minimal_survey()
    survey.inferences[0].citations = [Citation(ref_type="FACT", ref="config_files: []")]
    ok, errors = RecoveryValidator().validate_survey(
        survey,
        behavior_ids=set(),
        fact_ids=aliases | statements,
        fact_statements=statements,
        entity_keys=set(),
    )
    assert ok, errors


_ENTITY_KEYS = {
    "CLASS:app/models/ticket.py:app.models.ticket.Ticket",
    "FILE:app/db.py:app/db.py",
    "MODULE:app/db.py:",
}


def test_dotted_class_member_and_garbled_file_refs_resolve() -> None:
    survey = _minimal_survey()
    survey.inferences[0].citations = [
        Citation(ref_type="CODE_ENTITY", ref="app.models.ticket.Ticket.status"),
        Citation(ref_type="CODE_ENTITY", ref="FILE:app/db.py:app.db.py"),
    ]
    ok, errors = RecoveryValidator().validate_survey(
        survey,
        behavior_ids=set(),
        fact_ids=set(),
        fact_statements=set(),
        entity_keys=_ENTITY_KEYS,
    )
    assert ok, errors


def test_dotted_ref_to_unindexed_class_still_errors() -> None:
    survey = _minimal_survey()
    survey.inferences[0].citations = [
        Citation(ref_type="CODE_ENTITY", ref="app.models.user.User.email"),
    ]
    ok, errors = RecoveryValidator().validate_survey(
        survey,
        behavior_ids=set(),
        fact_ids=set(),
        fact_statements=set(),
        entity_keys=_ENTITY_KEYS,
    )
    assert not ok
    assert errors == ["UNKNOWN_ENTITY:app.models.user.User.email"]


def _feature(ac_citations: list[list[Citation]]) -> RecoveredFeatureSpec:
    return RecoveredFeatureSpec(
        feature_ref="F-1",
        body=FeatureSpecBody(behavior="b", summary="s", inputs=[], outputs=[], rules=[]),
        rule_citations={},
        requirements=[],
        acceptance_criteria=[
            RecoveredAcDraft(ref=f"AC-{i}", statement="st", citations=cits, confidence="MEDIUM")
            for i, cits in enumerate(ac_citations, start=1)
        ],
        principal_entity_links=[
            PrincipalEntityLink(stable_key="CLASS:app/models/ticket.py:app.models.ticket.Ticket"),
            PrincipalEntityLink(stable_key="CLASS:app/nowhere.py:app.nowhere.Ghost"),
        ],
        inferences=[],
        uncertainties=[],
        confidence="MEDIUM",
    )


def test_prune_drops_unsupported_citations_acs_and_links() -> None:
    good = Citation(ref_type="OBSERVED_BEHAVIOR", ref="OB-0001")
    bad = Citation(ref_type="FACT", ref="fastapi/sqlalchemy/pytest stack from discovery summary")
    survey = _minimal_survey()
    survey.inferences[0].citations = [bad]
    feature = _feature([[good, bad], [bad]])

    pruned_survey, specs, pruned = RecoveryValidator().prune_unsupported(
        survey,
        [feature],
        behavior_ids={"OB-0001"},
        fact_ids=set(),
        fact_statements=set(),
        entity_keys=_ENTITY_KEYS,
    )

    assert pruned_survey.inferences == []
    assert len(specs) == 1
    assert [ac.ref for ac in specs[0].acceptance_criteria] == ["AC-1"]
    assert specs[0].acceptance_criteria[0].citations == [good]
    assert [link.stable_key for link in specs[0].principal_entity_links] == [
        "CLASS:app/models/ticket.py:app.models.ticket.Ticket"
    ]
    removed = {p["removed"] for p in pruned}
    assert {"citation", "inference", "acceptance_criterion", "entity_link"} <= removed
    ok, errors, _ = RecoveryValidator().validate_feature_spec(
        specs[0],
        behavior_ids={"OB-0001"},
        fact_ids=set(),
        fact_statements=set(),
        entity_keys=_ENTITY_KEYS,
        behavior_kinds={},
    )
    assert ok, errors


def test_prune_removes_feature_without_supported_acs() -> None:
    bad = Citation(ref_type="OBSERVED_BEHAVIOR", ref="OB-9999")
    _, specs, pruned = RecoveryValidator().prune_unsupported(
        _minimal_survey(),
        [_feature([[bad]])],
        behavior_ids={"OB-0001"},
        fact_ids=set(),
        fact_statements=set(),
        entity_keys=_ENTITY_KEYS,
    )
    assert specs == []
    assert {"where": "feature:F-1", "removed": "feature", "error": "NO_SUPPORTED_ACS"} in pruned


def test_unknown_behavior_citation_errors() -> None:
    survey = _minimal_survey()
    ok, errors = RecoveryValidator().validate_survey(
        survey,
        behavior_ids=set(),
        fact_ids=set(),
        fact_statements=set(),
        entity_keys=set(),
    )
    assert not ok
    assert any("UNKNOWN_BEHAVIOR" in e for e in errors)


_INDEX = {
    "ROUTE:POST /tickets",
    "ROUTE:PATCH /tickets/{ticket_id}",
    "FUNCTION:app/api/tickets.py:app.api.tickets.create_ticket",
    "FUNCTION:app/api/tickets.py:app.api.tickets.update_ticket",
    "FUNCTION:app/api/tickets.py:app.api.tickets.get_db",
    "FUNCTION:app/db.py:app.db.get_db",
    "CLASS:app/models/ticket.py:app.models.ticket.Ticket",
    "ORM_MODEL:app/models/ticket.py:app.models.ticket.Ticket",
    "METHOD:app/services/ticket_service.py:app.services.ticket_service.TicketService.update_status",
    "TEST:tests/test_tickets_api.py:tests.test_tickets_api.test_create_ticket",
}


def test_canonical_entity_keys_resolves_model_ref_forms() -> None:
    model = [
        "CLASS:app/models/ticket.py:app.models.ticket.Ticket",
        "ORM_MODEL:app/models/ticket.py:app.models.ticket.Ticket",
    ]
    assert canonical_entity_keys("ROUTE:POST /tickets", _INDEX) == ["ROUTE:POST /tickets"]
    assert canonical_entity_keys("ROUTE POST /tickets", _INDEX) == ["ROUTE:POST /tickets"]
    assert canonical_entity_keys("POST /tickets", _INDEX) == ["ROUTE:POST /tickets"]
    assert canonical_entity_keys("app/models/ticket.py:app.models.ticket.Ticket", _INDEX) == model
    assert canonical_entity_keys("app.models.ticket.Ticket", _INDEX) == model
    assert canonical_entity_keys("app/api/tickets.py:create_ticket", _INDEX) == [
        "FUNCTION:app/api/tickets.py:app.api.tickets.create_ticket"
    ]
    assert canonical_entity_keys("tests/test_tickets_api.py::test_create_ticket", _INDEX) == [
        "TEST:tests/test_tickets_api.py:tests.test_tickets_api.test_create_ticket"
    ]
    assert canonical_entity_keys("TicketService.update_status", _INDEX) == [
        "METHOD:app/services/ticket_service.py:app.services.ticket_service.TicketService.update_status"
    ]
    assert canonical_entity_keys("get_db", _INDEX) == [], "ambiguous short name"
    assert canonical_entity_keys("", _INDEX) == []
    assert canonical_entity_keys("app/api/tickets.py:delete_ticket", _INDEX) == []


def test_prune_links_canonical_keys_survey_entities_and_routes() -> None:
    survey = _minimal_survey()
    survey.features = [
        RecoveredFeatureDraft(
            ref="F-1",
            capability_ref="C-1",
            name="Create ticket",
            description="d",
            principal_entities=["app/api/tickets.py:create_ticket", "TicketCreate"],
            supporting_behaviors=["OB-0001"],
        )
    ]
    feature = _feature([[Citation(ref_type="OBSERVED_BEHAVIOR", ref="OB-0001")]])
    feature.principal_entity_links = [
        PrincipalEntityLink(stable_key="app.models.ticket.Ticket", confidence=0.9)
    ]
    _, specs, _ = RecoveryValidator().prune_unsupported(
        survey,
        [feature],
        behavior_ids={"OB-0001"},
        fact_ids=set(),
        fact_statements=set(),
        entity_keys=_INDEX,
        principal_aliases={
            "FUNCTION:app/api/tickets.py:app.api.tickets.create_ticket": ["ROUTE:POST /tickets"]
        },
    )
    links = {link.stable_key: link.confidence for link in specs[0].principal_entity_links}
    assert links == {
        "CLASS:app/models/ticket.py:app.models.ticket.Ticket": 0.9,
        "ORM_MODEL:app/models/ticket.py:app.models.ticket.Ticket": 0.9,
        "FUNCTION:app/api/tickets.py:app.api.tickets.create_ticket": 0.5,
        "ROUTE:POST /tickets": 0.5,
    }


def test_keyless_entity_links_are_dropped_on_parse() -> None:
    spec = RecoveredFeatureSpec.model_validate(
        {
            **_feature([[Citation(ref_type="OBSERVED_BEHAVIOR", ref="OB-0001")]]).model_dump(),
            "principal_entity_links": [{}, {"stable_key": "ROUTE:POST /tickets"}],
        }
    )
    assert [link.stable_key for link in spec.principal_entity_links] == ["ROUTE:POST /tickets"]
