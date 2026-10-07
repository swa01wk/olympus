from __future__ import annotations

from typing import Any

from agents.scout.schemas import (
    CapabilityDraft,
    Citation,
    InferenceDraft,
    RecoveredAcDraft,
    RecoveredFeatureDraft,
    RecoveredFeatureSpec,
    RepositorySurvey,
    RequirementDraft,
    UncertaintyDraft,
)
from core.planning.schemas import ArchitectureBody, TechnologyStack
from core.product_model.schemas import FeatureSpecBody


def minimal_architecture_body() -> ArchitectureBody:
    return ArchitectureBody(
        summary="SupportDesk API recovered from repository structure.",
        technology_stack=TechnologyStack(
            language="python",
            web="fastapi",
            orm="sqlalchemy",
            tests="pytest",
        ),
        components=[],
        layers=[],
        dependency_rules=[],
        directory_conventions=[],
        decisions=[],
        constraints=[],
        risks=[],
    )


def build_survey_payload(
    *,
    behavior_key: str,
    fact_ref: str,
    route_key: str = "ROUTE:POST /tickets",
) -> dict[str, Any]:
    survey = RepositorySurvey(
        recovered_architecture=minimal_architecture_body(),
        capabilities=[CapabilityDraft(ref="CAP-1", name="Tickets", description="Ticket lifecycle")],
        features=[
            RecoveredFeatureDraft(
                ref="FEAT-1",
                capability_ref="CAP-1",
                name="Create ticket",
                description="POST /tickets",
                principal_entities=[route_key],
                supporting_behaviors=[behavior_key],
            )
        ],
        inferences=[
            InferenceDraft(
                statement="Ticket creation is exposed via HTTP POST.",
                citations=[Citation(ref_type="OBSERVED_BEHAVIOR", ref=behavior_key)],
                confidence="MEDIUM",
            )
        ],
        uncertainties=[
            UncertaintyDraft(
                question="What is the semantics of ticket escalation?",
                why_uncertain="Escalate endpoint exists without tests.",
                citations=[Citation(ref_type="FACT", ref=fact_ref)],
                blocking_suggested=True,
            )
        ],
    )
    return survey.model_dump(mode="json")


def build_recover_feature_payload(
    *,
    behavior_key: str,
    route_key: str = "ROUTE:POST /tickets",
) -> dict[str, Any]:
    spec = RecoveredFeatureSpec(
        feature_ref="FEAT-1",
        body=FeatureSpecBody(
            behavior="Create a support ticket",
            summary="POST /tickets creates a ticket",
            inputs=["title"],
            outputs=["ticket id"],
            rules=["Return 201 on success"],
            constraints=[],
            out_of_scope=[],
        ),
        rule_citations={},
        requirements=[
            RequirementDraft(
                ref="REQ-1",
                statement="API accepts ticket creation requests",
                citations=[Citation(ref_type="OBSERVED_BEHAVIOR", ref=behavior_key)],
            )
        ],
        acceptance_criteria=[
            RecoveredAcDraft(
                ref="AC-1",
                statement="Creating a ticket returns 201",
                when="POST /tickets with valid body",
                then="response status is 201",
                citations=[Citation(ref_type="OBSERVED_BEHAVIOR", ref=behavior_key)],
                confidence="MEDIUM",
            )
        ],
        implementation=None,
        principal_entity_links=[{"stable_key": route_key, "confidence": 0.75}],
        inferences=[],
        uncertainties=[
            UncertaintyDraft(
                question="Should escalation mutate ticket status?",
                why_uncertain="No automated test covers escalation.",
                citations=[Citation(ref_type="CODE_ENTITY", ref=route_key)],
                blocking_suggested=False,
            )
        ],
        confidence="MEDIUM",
    )
    return spec.model_dump(mode="json")
