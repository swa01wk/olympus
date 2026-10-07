from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.integrations.inbound.envelope import InboundEventEnvelope


class InboundAdapter(Protocol):
    source_type: str

    async def authenticate(
        self, session: AsyncSession, raw: dict[str, Any], ctx: CommandContext | None
    ) -> tuple[bool, str | None]: ...

    async def validate(
        self, session: AsyncSession, raw: dict[str, Any]
    ) -> tuple[bool, str | None]: ...

    async def normalize(
        self, session: AsyncSession, raw: dict[str, Any]
    ) -> InboundEventEnvelope: ...

    async def to_command(
        self, session: AsyncSession, envelope: InboundEventEnvelope, normalized: dict[str, Any]
    ) -> tuple[str, str, str, dict[str, Any]]: ...


class InboundAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, InboundAdapter] = {}

    def register(self, adapter: InboundAdapter) -> None:
        self._adapters[adapter.source_type] = adapter

    def get(self, source_type: str) -> InboundAdapter | None:
        return self._adapters.get(source_type)


AdapterFactory = Callable[[], InboundAdapter]

_registry: InboundAdapterRegistry | None = None


def get_inbound_registry() -> InboundAdapterRegistry:
    global _registry
    if _registry is None:
        _registry = InboundAdapterRegistry()
        from core.integrations.inbound.adapters.change_request_api import ChangeRequestApiAdapter
        from core.integrations.inbound.adapters.ci_callback import CiCallbackAdapter
        from core.integrations.inbound.adapters.defect_report_api import DefectReportApiAdapter
        from core.integrations.inbound.adapters.document_upload import DocumentUploadAdapter
        from core.integrations.inbound.adapters.git_provider_webhook import (
            GitProviderWebhookAdapter,
        )
        from core.integrations.inbound.adapters.issue_tracker_webhook import (
            IssueTrackerWebhookAdapter,
        )

        _registry.register(DocumentUploadAdapter())
        _registry.register(ChangeRequestApiAdapter())
        _registry.register(DefectReportApiAdapter())
        _registry.register(GitProviderWebhookAdapter())
        _registry.register(IssueTrackerWebhookAdapter())
        _registry.register(CiCallbackAdapter())
    return _registry
