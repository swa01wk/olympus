from __future__ import annotations

from core.planning.schemas import (
    AcCoverageEntry,
    ApiDef,
    ArchitectureBody,
    ArchitectureProposal,
    ComponentDef,
    ContractDraft,
    DecisionDef,
    DirectoryConventionEntry,
    ImplementationSpecBody,
    ImplementationSpecDraft,
    TaskDraft,
    TaskPlan,
    TechnologyStack,
    TestRequirement,
)


def supportdesk_architecture_proposal() -> ArchitectureProposal:
    return ArchitectureProposal(
        body=ArchitectureBody(
            summary="SupportDesk FastAPI service",
            technology_stack=TechnologyStack(
                language="python3.12",
                web="fastapi",
                orm="sqlalchemy",
                tests="pytest",
            ),
            components=[
                ComponentDef(
                    name="api",
                    layer="api",
                    responsibility="HTTP routes",
                    directory="app/api",
                ),
                ComponentDef(
                    name="service",
                    layer="service",
                    responsibility="Business logic",
                    directory="app/service",
                ),
                ComponentDef(
                    name="models",
                    layer="persistence",
                    responsibility="ORM models",
                    directory="app/models",
                ),
            ],
            layers=["api", "service", "persistence"],
            dependency_rules=["api -> service", "service -> persistence"],
            directory_conventions=[
                DirectoryConventionEntry(path="app/api", purpose="routes"),
                DirectoryConventionEntry(path="app/service", purpose="services"),
                DirectoryConventionEntry(path="app/models", purpose="models"),
                DirectoryConventionEntry(path="tests/", purpose="pytest"),
            ],
            decisions=[
                DecisionDef(
                    id="D-1",
                    title="Stack",
                    decision="FastAPI + SQLAlchemy",
                    rationale="PRD NFRs",
                )
            ],
            constraints=["Use async SQLAlchemy where applicable"],
        ),
        contracts=[
            ContractDraft(
                key="create-ticket",
                kind="API",
                name="Create ticket",
                method="POST",
                path="/tickets",
            )
        ],
    )


def create_ticket_implementation_spec() -> ImplementationSpecDraft:
    return ImplementationSpecDraft(
        body=ImplementationSpecBody(
            summary="Create ticket endpoint and service",
            components=["api", "service", "models"],
            apis=[ApiDef(method="POST", path="/tickets", contract_key="create-ticket")],
            required_tests=[
                TestRequirement(
                    kind="api",
                    ac_keys=["AC-1"],
                    description="POST /tickets creates ticket",
                )
            ],
            file_scope=["app/api/**", "app/service/**", "app/models/**", "tests/**"],
            architecture_refs=["api", "create-ticket", "D-1"],
            ac_coverage=[
                AcCoverageEntry(ac_key="AC-1", locations=["api", "POST /tickets test"]),
            ],
        )
    )


def minimal_task_plan(impl_lineage: str = "SPEC-IMPL-FEAT-1") -> TaskPlan:
    return TaskPlan(
        tasks=[
            TaskDraft(
                ref="T-1",
                title="Implement create ticket",
                objective="Implement create ticket flow",
                implementation_spec_ref=impl_lineage,
                ac_refs=["AC-1"],
                allowed_scope=["app/api/**", "tests/**"],
                required_outputs=["candidate_commit", "changed_files", "test_results"],
                verification_requirements=["pytest passes for ticket creation"],
                estimated_size="M",
            )
        ],
    )
