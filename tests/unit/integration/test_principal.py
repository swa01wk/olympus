from __future__ import annotations

import uuid

from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.models import CodeEntity
from core.traceability.spec_code_links.principal import is_principal_entity


def _entity(**kwargs: object) -> CodeEntity:
    defaults = {
        "index_version_id": uuid.uuid4(),
        "stable_key": "k",
        "type": EntityType.FUNCTION,
        "qualified_name": "mod.fn",
        "is_public": True,
    }
    defaults.update(kwargs)
    return CodeEntity(**defaults)  # type: ignore[arg-type]


def test_private_helper_excluded() -> None:
    ent = _entity(qualified_name="mod._helper", type=EntityType.FUNCTION, is_public=False)
    assert is_principal_entity(ent, set()) is False


def test_route_included() -> None:
    ent = _entity(type=EntityType.ROUTE, qualified_name="GET /tickets")
    assert is_principal_entity(ent, set()) is True


def test_declared_method_included() -> None:
    ent = _entity(type=EntityType.METHOD, qualified_name="TicketService.create")
    assert is_principal_entity(ent, {"create"}) is True
