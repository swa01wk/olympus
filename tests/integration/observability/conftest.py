from __future__ import annotations

from collections.abc import Iterator

import pytest
from core.observability.testing import in_memory_tracer
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture(scope="module")
def memory_span_exporter() -> Iterator[InMemorySpanExporter]:
    with in_memory_tracer() as exporter:
        yield exporter
