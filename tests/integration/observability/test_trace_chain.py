from __future__ import annotations

import uuid

import pytest
from core.integrations.connectors.base import ConnectorAction, ConnectorHealth, ConnectorResult
from core.integrations.connectors.registry import ConnectorRegistry
from core.observability.instrumentation import (
    STANDARD_ATTRS,
    command_span,
    connector_span,
    execution_span,
    model_call_span,
    scheduler_span,
    tool_span,
)
from core.state.transition_service import TransitionService
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

pytestmark = pytest.mark.integration


def _names(exporter: InMemorySpanExporter) -> set[str]:
    return {s.name for s in exporter.get_finished_spans()}


def test_linked_spans_share_trace_id(memory_span_exporter: InMemorySpanExporter) -> None:
    memory_span_exporter.clear()
    corr = str(uuid.uuid4())
    eid = str(uuid.uuid4())
    with (
        command_span("delivery_cycle.start", correlation_id=corr),
        model_call_span(alias="planning", provider="openai", model="m", execution_id=eid),
        tool_span(tool="repo.read", execution_id=eid),
    ):
        pass
    spans = memory_span_exporter.get_finished_spans()
    assert len(spans) == 3
    trace_ids = {s.context.trace_id for s in spans if s.context is not None}
    assert len(trace_ids) == 1


def test_instrumentation_chain_covers_standard_span_kinds(
    memory_span_exporter: InMemorySpanExporter,
) -> None:
    memory_span_exporter.clear()
    corr = "trace-chain-1"
    exec_id = str(uuid.uuid4())
    with (
        command_span("delivery_cycle.cancel", correlation_id=corr, project_id=str(uuid.uuid4())),
        scheduler_span(correlation_id=corr),
        execution_span(execution_id=exec_id, correlation_id=corr),
        model_call_span(
            alias="planning",
            provider="openai",
            model="gpt-test",
            execution_id=exec_id,
            provider_request_id="req-1",
        ),
        tool_span(tool="repo.read", execution_id=exec_id),
        connector_span(
            connector="git_local",
            action="fetch",
            connector_action_id=str(uuid.uuid4()),
            execution_id=exec_id,
            correlation_id=corr,
        ),
    ):
        pass
    names = _names(memory_span_exporter)
    assert names >= {
        "olympus.command",
        "olympus.scheduler",
        "olympus.execution",
        "olympus.model_call",
        "olympus.tool_gateway",
        "olympus.connector",
    }


def test_standard_attribute_keys_documented() -> None:
    assert "olympus.correlation_id" in STANDARD_ATTRS
    assert "olympus.execution_id" in STANDARD_ATTRS


@pytest.mark.asyncio
async def test_command_transition_emits_command_span(
    db_session,
    operator_ctx,
    memory_span_exporter: InMemorySpanExporter,
) -> None:
    from core.domain.delivery_cycles.models import DeliveryCycle
    from core.domain.enums import DeliveryCycleType
    from core.domain.projects.models import Project

    memory_span_exporter.clear()
    project = Project(key="otel-p", name="Otel")
    db_session.add(project)
    await db_session.flush()
    cycle = DeliveryCycle(
        project_id=project.id,
        key="DC-OTEL",
        type=DeliveryCycleType.GREENFIELD_BUILD,
        objective="otel",
        state="DISCOVERY",
        state_version=0,
        opened_by_actor_id=operator_ctx.actor.id,
    )
    db_session.add(cycle)
    await db_session.flush()
    svc = TransitionService()
    await svc.transition(
        db_session,
        "delivery_cycle",
        cycle.id,
        "DISCOVERY",
        "cancel",
        operator_ctx,
    )
    assert "olympus.command" in _names(memory_span_exporter)


class _EchoConnector:
    name = "echo_test"
    actions = {"ping"}

    async def validate(self) -> ConnectorHealth:
        return ConnectorHealth(ok=True)

    async def reconcile(self, request: object) -> ConnectorResult:
        return ConnectorResult(status="SUCCEEDED", normalized_result={})

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        return ConnectorResult(status="SUCCEEDED", normalized_result={"ok": True})


@pytest.mark.asyncio
async def test_connector_registry_emits_connector_span(
    db_session,
    memory_span_exporter: InMemorySpanExporter,
) -> None:
    from core.domain.actors.models import Actor
    from core.domain.enums import ActorKind, ActorRole

    memory_span_exporter.clear()
    actor = Actor(kind=ActorKind.SYSTEM, name="conn-span", roles=[ActorRole.SYSTEM.value])
    db_session.add(actor)
    await db_session.flush()
    reg = ConnectorRegistry()
    reg.register(_EchoConnector())
    action = ConnectorAction(
        connector="echo_test",
        action="ping",
        target_resource="test",
        inputs={},
        idempotency_key="idem-1",
        correlation_id="corr-conn",
        expected_result_schema="none",
    )
    await reg.execute_with_persistence(db_session, action, actor_id=actor.id)
    assert "olympus.connector" in _names(memory_span_exporter)
