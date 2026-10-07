from __future__ import annotations

from agents.scout.schemas import Citation, InferenceDraft, RepositorySurvey
from core.intelligence.recovered_specs.validation import (
    RecoveryValidator,
    discovery_fact_aliases,
)
from core.planning.schemas import ArchitectureBody, TechnologyStack


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
