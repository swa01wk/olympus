"""In-memory OTel exporter for integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@contextmanager
def in_memory_tracer(service_name: str = "olympus-test") -> Iterator[InMemorySpanExporter]:
    import core.observability.otel as otel_mod

    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    previous = trace.get_tracer_provider()
    otel_mod._configured = False
    otel_mod._tracer = None
    trace.set_tracer_provider(provider)
    try:
        yield exporter
    finally:
        provider.force_flush()
        otel_mod._configured = False
        otel_mod._tracer = None
        trace.set_tracer_provider(previous)
