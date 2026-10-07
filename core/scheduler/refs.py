from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.task_contracts.schemas import VersionedRef


class RefResolver(Protocol):
    ref_type: str

    async def exists(self, session: AsyncSession, ref: VersionedRef) -> bool: ...

    async def is_current(self, session: AsyncSession, ref: VersionedRef) -> bool: ...


class RefResolverRegistry:
    def __init__(self) -> None:
        self._resolvers: dict[str, RefResolver] = {}

    def register(self, resolver: RefResolver) -> None:
        self._resolvers[resolver.ref_type] = resolver

    def get(self, ref_type: str) -> RefResolver | None:
        return self._resolvers.get(ref_type)

    async def resolve_checks(
        self, session: AsyncSession, refs: list[VersionedRef]
    ) -> tuple[
        dict[tuple[str, uuid.UUID, int | None], bool],
        dict[tuple[str, uuid.UUID, int | None], bool],
    ]:
        exists: dict[tuple[str, uuid.UUID, int | None], bool] = {}
        current: dict[tuple[str, uuid.UUID, int | None], bool] = {}
        for ref in refs:
            key = (ref.ref_type, ref.ref_id, ref.version)
            resolver = self.get(ref.ref_type)
            if resolver is None:
                exists[key] = False
                current[key] = False
                continue
            exists[key] = await resolver.exists(session, ref)
            current[key] = await resolver.is_current(session, ref)
        return exists, current


def build_default_registry() -> RefResolverRegistry:
    from core.assurance.refs import FindingRefResolver, VerificationPlanRefResolver
    from core.integration.refs import IntegrationCandidateRefResolver
    from core.planning.refs import ArchitectureRefResolver, ImplementationSpecRefResolver
    from core.product_model.defects.refs import DefectRefResolver
    from core.product_model.refs import (
        AcceptanceCriterionRefResolver,
        FeatureSpecRefResolver,
        ProductSourceVersionRefResolver,
        RequirementRefResolver,
    )
    from core.release.refs import ReleaseRefResolver
    from core.scheduler.resolvers import (
        ArtifactRefResolver,
        DeliveryCycleRefResolver,
        TaskContractRefResolver,
    )

    registry = RefResolverRegistry()
    registry.register(ReleaseRefResolver())
    registry.register(IntegrationCandidateRefResolver())
    registry.register(FindingRefResolver())
    registry.register(VerificationPlanRefResolver())
    registry.register(ArtifactRefResolver())
    registry.register(DeliveryCycleRefResolver())
    registry.register(TaskContractRefResolver())
    registry.register(ProductSourceVersionRefResolver())
    registry.register(FeatureSpecRefResolver())
    registry.register(RequirementRefResolver())
    registry.register(AcceptanceCriterionRefResolver())
    registry.register(DefectRefResolver())
    registry.register(ArchitectureRefResolver())
    registry.register(ImplementationSpecRefResolver())
    return registry
