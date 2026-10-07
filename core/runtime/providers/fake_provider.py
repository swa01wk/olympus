from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from core.config.settings import get_settings
from core.runtime.contracts import ProviderRequest, ProviderResponse
from core.runtime.errors import (
    ProviderAuthError,
    ProviderRateLimited,
    ProviderTransientError,
    RuntimeCancelled,
)


@dataclass
class FakeScriptStep:
    kind: str = "response"
    structured: dict[str, Any] | None = None
    raw_text: str | None = None
    input_tokens: int = 10
    output_tokens: int = 20
    provider_request_id: str = "fake-req"
    delay_s: float = 0
    error: Exception | None = None
    vectors: list[list[float]] = field(default_factory=list)


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        env = get_settings().olympus_env
        if env not in ("local", "test"):
            raise RuntimeError(f"FakeProvider is not allowed when OLYMPUS_ENV={env}")
        self._script: list[FakeScriptStep] = []
        self._cancel_event: asyncio.Event | None = None

    def set_script(self, steps: list[FakeScriptStep]) -> None:
        self._script = list(steps)

    def bind_cancel(self, event: asyncio.Event | None) -> None:
        self._cancel_event = event

    def _next_step(self) -> FakeScriptStep:
        if not self._script:
            return FakeScriptStep(
                structured={"title": "default", "bullet_points": ["a"], "word_count_estimate": 1}
            )
        return self._script.pop(0)

    async def complete(self, req: ProviderRequest) -> ProviderResponse:
        step = self._next_step()
        if step.delay_s:
            await asyncio.sleep(step.delay_s)
        if self._cancel_event and self._cancel_event.is_set():
            raise RuntimeCancelled()
        if step.error is not None:
            raise step.error
        structured = step.structured
        raw = step.raw_text
        if structured is None and raw is None:
            raw = json.dumps({})
        return ProviderResponse(
            raw_text=raw,
            structured=structured,
            tool_calls=[],
            input_tokens=step.input_tokens,
            output_tokens=step.output_tokens,
            provider_request_id=step.provider_request_id,
        )

    async def embed(
        self, texts: list[str], model: str
    ) -> tuple[list[list[float]], int, str | None]:
        step = self._next_step()
        if step.error is not None:
            raise step.error
        vectors = step.vectors or [[0.1, 0.2, 0.3] for _ in texts]
        return vectors, step.input_tokens, step.provider_request_id


def fake_rate_limit(retry_after: float = 1.0) -> ProviderRateLimited:
    return ProviderRateLimited("rate limited", retry_after=retry_after)


def fake_auth_error() -> ProviderAuthError:
    return ProviderAuthError("unauthorized")


def fake_transient() -> ProviderTransientError:
    return ProviderTransientError("transient failure")
