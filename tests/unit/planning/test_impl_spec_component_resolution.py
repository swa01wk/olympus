"""Implementation-spec drafts that name code instead of components are mapped back."""

from __future__ import annotations

import pytest
from core.planning.completion import _resolve_component
from core.planning.schemas import ComponentDef


def _comp(name: str, directory: str) -> ComponentDef:
    return ComponentDef(name=name, layer="l", responsibility="r", directory=directory)


COMPONENTS = [
    _comp("API routes", "app/api"),
    _comp("Ticket service", "app/services"),
    _comp("Paging notification service", "app/services"),
    _comp("Ticket repository", "app/repositories"),
    _comp("Ticket ORM model", "app/models"),
    _comp("Ticket schemas", "app/schemas"),
    _comp("Application entry point", "app"),
    _comp("Paging integration client", "app/integrations"),
]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ticket service", "Ticket service"),
        ("app.services.ticket_service.TicketService", "Ticket service"),
        (
            "app.services.paging_notification_service.PagingNotificationService",
            "Paging notification service",
        ),
        ("app.integrations.paging_client.PagingIntegrationClient", "Paging integration client"),
        ("app.repositories.ticket_repository.TicketRepository", "Ticket repository"),
        ("app.models.ticket.Ticket", "Ticket ORM model"),
        ("app.schemas.ticket.TicketUpdate", "Ticket schemas"),
        ("app/api/tickets.py", "API routes"),
        ("app.main", "Application entry point"),
    ],
)
def test_code_reference_maps_to_component(raw: str, expected: str) -> None:
    assert _resolve_component(raw, COMPONENTS) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "app.services.billing.BillingService",
        "app.workers.digest.DigestWorker",
        "Notification hub",
    ],
)
def test_unresolvable_names_are_left_for_conformance(raw: str) -> None:
    assert _resolve_component(raw, COMPONENTS) == raw
