"""Shared span helpers for model, tool, and command paths."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from core.observability.context import bind
from core.observability.otel import span

STANDARD_ATTRS = (
    "olympus.project_id",
    "olympus.delivery_cycle_id",
    "olympus.feature_spec_id",
    "olympus.task_id",
    "olympus.task_contract_version",
    "olympus.execution_id",
    "olympus.snapshot_id",
    "olympus.integration_candidate_id",
    "olympus.commit_sha",
    "olympus.provider_request_id",
    "olympus.connector_action_id",
    "olympus.correlation_id",
)


def _std_attrs(**kwargs: str | None) -> dict[str, str]:
    mapping = {
        "project_id": "olympus.project_id",
        "delivery_cycle_id": "olympus.delivery_cycle_id",
        "feature_spec_id": "olympus.feature_spec_id",
        "task_id": "olympus.task_id",
        "task_contract_version": "olympus.task_contract_version",
        "execution_id": "olympus.execution_id",
        "snapshot_id": "olympus.snapshot_id",
        "integration_candidate_id": "olympus.integration_candidate_id",
        "commit_sha": "olympus.commit_sha",
        "provider_request_id": "olympus.provider_request_id",
        "connector_action_id": "olympus.connector_action_id",
        "correlation_id": "olympus.correlation_id",
    }
    out: dict[str, str] = {}
    for key, value in kwargs.items():
        if value is None:
            continue
        attr = mapping.get(key, key)
        out[attr] = value
    return out


@contextmanager
def api_span(
    *,
    route: str,
    correlation_id: str | None = None,
    project_id: str | None = None,
) -> Iterator[Any]:
    bind(correlation_id=correlation_id, olympus_project_id=project_id)
    with span(
        "olympus.api",
        route=route,
        **_std_attrs(correlation_id=correlation_id, project_id=project_id),
    ) as s:
        yield s


@contextmanager
def command_span(
    command: str,
    *,
    project_id: str | None = None,
    delivery_cycle_id: str | None = None,
    correlation_id: str | None = None,
) -> Iterator[Any]:
    bind(
        correlation_id=correlation_id,
        olympus_project_id=project_id,
        olympus_delivery_cycle_id=delivery_cycle_id,
    )
    with span(
        "olympus.command",
        command=command,
        **_std_attrs(
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            correlation_id=correlation_id,
        ),
    ) as s:
        yield s


@contextmanager
def scheduler_span(*, admitted: int = 0, correlation_id: str | None = None) -> Iterator[Any]:
    bind(correlation_id=correlation_id)
    with span(
        "olympus.scheduler",
        admitted=str(admitted),
        **_std_attrs(correlation_id=correlation_id),
    ) as s:
        yield s


@contextmanager
def execution_span(
    *,
    execution_id: str | None = None,
    snapshot_id: str | None = None,
    task_id: str | None = None,
    correlation_id: str | None = None,
) -> Iterator[Any]:
    bind(
        olympus_execution_id=execution_id,
        olympus_snapshot_id=snapshot_id,
        olympus_task_id=task_id,
    )
    with span(
        "olympus.execution",
        **_std_attrs(
            execution_id=execution_id,
            snapshot_id=snapshot_id,
            task_id=task_id,
            correlation_id=correlation_id,
        ),
    ) as s:
        yield s


@contextmanager
def model_call_span(
    *,
    alias: str,
    provider: str,
    model: str,
    execution_id: str | None = None,
    provider_request_id: str | None = None,
) -> Iterator[Any]:
    bind(olympus_execution_id=execution_id)
    with span(
        "olympus.model_call",
        alias=alias,
        provider=provider,
        model=model,
        **_std_attrs(
            execution_id=execution_id,
            provider_request_id=provider_request_id,
        ),
    ) as s:
        yield s


@contextmanager
def tool_span(*, tool: str, execution_id: str | None = None) -> Iterator[Any]:
    bind(olympus_execution_id=execution_id)
    with span(
        "olympus.tool_gateway",
        tool=tool,
        **_std_attrs(execution_id=execution_id),
    ) as s:
        yield s


@contextmanager
def connector_span(
    *,
    connector: str,
    action: str,
    connector_action_id: str | None = None,
    execution_id: str | None = None,
    correlation_id: str | None = None,
) -> Iterator[Any]:
    bind(olympus_execution_id=execution_id, olympus_connector_action_id=connector_action_id)
    with span(
        "olympus.connector",
        connector=connector,
        action=action,
        **_std_attrs(
            connector_action_id=connector_action_id,
            execution_id=execution_id,
            correlation_id=correlation_id,
        ),
    ) as s:
        yield s
