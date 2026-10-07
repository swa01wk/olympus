"""OpenTelemetry setup — no-op when OTLP endpoint is unset."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from core.config.settings import OlympusSettings, get_settings
from core.observability.context import merged_context

_configured = False
_tracer: Any = None


def configure_otel(settings: OlympusSettings | None = None) -> None:
    global _configured, _tracer
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider

    existing = otel_trace.get_tracer_provider()
    if isinstance(existing, SdkTracerProvider):
        _tracer = otel_trace.get_tracer("olympus")
        _configured = True
        return
    if _configured:
        return
    cfg = settings or get_settings()
    endpoint = (cfg.otel_exporter_otlp_endpoint or "").strip()
    if not endpoint:
        _configured = True
        _tracer = None
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            "service.name": cfg.service_name,
            "deployment.environment": cfg.olympus_env,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("olympus")
    _configured = True


def get_tracer() -> Any:
    configure_otel()
    return _tracer


@contextmanager
def span(name: str, **attributes: str | int | float | bool | None) -> Iterator[Any]:
    configure_otel()
    from opentelemetry import trace as otel_trace

    tracer = _tracer if _tracer is not None else otel_trace.get_tracer("olympus")
    attrs = {k: v for k, v in {**merged_context(), **attributes}.items() if v is not None}
    with tracer.start_as_current_span(name, attributes=attrs) as current:
        yield current


def inject_trace_context() -> dict[str, str] | None:
    configure_otel()
    if _tracer is None:
        return None
    from opentelemetry import context as otel_context
    from opentelemetry.propagate import inject

    carrier: dict[str, str] = {}
    inject(carrier, context=otel_context.get_current())
    return carrier or None
