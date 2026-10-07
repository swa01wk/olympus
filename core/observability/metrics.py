"""Prometheus metrics for operational visibility."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest

TOOLGATEWAY_DENIALS = Counter(
    "olympus_toolgateway_denials_total",
    "ToolGateway denials by reason",
    ["reason"],
)
LEASE_EXPIRIES = Counter(
    "olympus_lease_expiries_total",
    "Execution lease expiries",
)
CONNECTOR_UNKNOWN = Counter(
    "olympus_connector_unknown_total",
    "Connector outcomes marked UNKNOWN",
    ["connector"],
)
LLM_TOKENS = Counter(
    "olympus_llm_tokens_total",
    "LLM tokens by alias and direction",
    ["alias", "direction"],
)
LLM_SCHEMA_FAILURES = Counter(
    "olympus_llm_schema_failures_total",
    "Schema validation failures on model output",
    ["alias"],
)
SCHEDULER_QUEUE = Gauge(
    "olympus_scheduler_queue_depth",
    "Tasks eligible or queued",
    ["status"],
)
EXECUTION_DURATION = Histogram(
    "olympus_execution_duration_seconds",
    "Execution duration by profile",
    ["profile"],
    buckets=(1, 5, 15, 60, 120, 300, 600, 1800),
)
INBOUND_EVENTS = Counter(
    "olympus_inbound_events_total",
    "Inbound events by status",
    ["status"],
)


def metrics_payload() -> bytes:
    return generate_latest()
