from __future__ import annotations

from typing import Protocol

from core.runtime.contracts import ProviderRequest, ProviderResponse


class ModelProvider(Protocol):
    name: str

    async def complete(self, req: ProviderRequest) -> ProviderResponse: ...

    async def embed(
        self, texts: list[str], model: str
    ) -> tuple[list[list[float]], int, str | None]: ...
