"""Exported command catalog for operator UI and Orchestrator."""

from __future__ import annotations

from typing import Any

from core.domain.enums import ActorRole

# Payload schemas are intentionally minimal (extra keys allowed at dispatch).
_CATALOG: list[dict[str, Any]] = [
    {
        "command": "create_project",
        "target_type": "project",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "key": {"type": "string"}},
            "required": ["name", "key"],
        },
    },
    {
        "command": "create_delivery_cycle",
        "target_type": "project",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "objective": {"type": "string"},
                "repository_id": {"type": "string"},
            },
            "required": ["type", "objective"],
        },
    },
    {
        "command": "delivery_cycle.transition",
        "target_type": "delivery_cycle",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "string"},
                "command_name": {"type": "string"},
                "expected_state": {"type": "string"},
                "payload": {"type": "object"},
            },
            "required": ["cycle_id", "command_name", "expected_state"],
        },
    },
    {
        "command": "approval.decide",
        "target_type": "approval",
        "required_roles": [ActorRole.APPROVER.value],
        "payload_schema": {
            "type": "object",
            "properties": {
                "approval_id": {"type": "string"},
                "decision": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["approval_id", "decision"],
        },
    },
    {
        "command": "approval.request",
        "target_type": "delivery_cycle",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {"type": "object"},
    },
    {
        "command": "register_repository",
        "target_type": "project",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {"type": "object"},
    },
    {
        "command": "retry_materialization",
        "target_type": "repository",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {"type": "object"},
    },
    {
        "command": "intake_change_request",
        "target_type": "project",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {"type": "object"},
    },
    {
        "command": "intake_defect",
        "target_type": "project",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {"type": "object"},
    },
    {
        "command": "attach_remote",
        "target_type": "delivery_cycle",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {"type": "object"},
    },
    {
        "command": "ingest_product_source",
        "target_type": "project",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {"type": "object"},
    },
    {
        "command": "request_scope_approval",
        "target_type": "delivery_cycle",
        "required_roles": [ActorRole.OPERATOR.value],
        "payload_schema": {"type": "object"},
    },
]


def list_registered_commands() -> list[str]:
    from core.commands.registry import build_command_bus

    return sorted(build_command_bus()._handlers.keys())  # noqa: SLF001


def export_command_catalog() -> dict[str, Any]:
    registered = set(list_registered_commands())
    entries = [e for e in _CATALOG if e["command"] in registered]
    for name in registered:
        if not any(e["command"] == name for e in entries):
            entries.append(
                {
                    "command": name,
                    "target_type": "unknown",
                    "required_roles": [ActorRole.OPERATOR.value],
                    "payload_schema": {"type": "object"},
                }
            )
    entries.sort(key=lambda e: e["command"])
    return {"commands": entries, "registered_count": len(registered)}
