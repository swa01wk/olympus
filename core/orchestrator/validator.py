from __future__ import annotations

import uuid
from typing import Any

from agents.orchestrator.schemas import OrchestratorTurn, ProposedCommand
from core.commands.catalog import export_command_catalog
from core.domain.actors.models import Actor


class OrchestratorValidationError(Exception):
    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def _catalog_by_name() -> dict[str, dict[str, Any]]:
    return {e["command"]: e for e in export_command_catalog()["commands"]}


def validate_turn(
    turn: OrchestratorTurn,
    *,
    actor: Actor,
    open_clarification_ids: set[str] | frozenset[str] | None = None,
    pending_approval_ids: set[str] | frozenset[str] | None = None,
) -> OrchestratorTurn:
    if turn.intent == "PROPOSE_COMMAND" and turn.proposed_command is not None:
        validate_proposed_command(turn.proposed_command, actor=actor)
    if turn.intent == "ANSWER_CLARIFICATION":
        if turn.clarification_answer_draft is None:
            raise OrchestratorValidationError(["CLARIFICATION_DRAFT_REQUIRED"])
        if open_clarification_ids is not None:
            cid = turn.clarification_answer_draft.clarification_id
            if cid not in open_clarification_ids:
                raise OrchestratorValidationError([f"UNKNOWN_CLARIFICATION:{cid}"])
    if turn.intent == "REVISION_NOTE_DRAFT":
        if turn.revision_note_draft is None:
            raise OrchestratorValidationError(["REVISION_NOTE_DRAFT_REQUIRED"])
        if not turn.revision_note_draft.note.strip():
            raise OrchestratorValidationError(["REVISION_NOTE_REQUIRED"])
        if pending_approval_ids is not None:
            aid = turn.revision_note_draft.approval_id
            if aid not in pending_approval_ids:
                raise OrchestratorValidationError([f"UNKNOWN_APPROVAL:{aid}"])
    return turn


def validate_proposed_command(proposal: ProposedCommand, *, actor: Actor) -> None:
    catalog = _catalog_by_name()
    entry = catalog.get(proposal.command)
    if entry is None:
        raise OrchestratorValidationError([f"UNKNOWN_COMMAND:{proposal.command}"])
    required_roles = entry.get("required_roles") or []
    if required_roles:
        actor_roles = set(actor.roles or [])
        if not actor_roles.intersection(required_roles):
            raise OrchestratorValidationError(["MISSING_ROLE"])
    if proposal.command == "approval.decide":
        raise OrchestratorValidationError(["APPROVAL_DECISION_REQUIRES_FORM"])
    if not isinstance(proposal.args, dict):
        raise OrchestratorValidationError(["ARGS_MUST_BE_OBJECT"])
    _ = uuid  # reserved for target_ref existence checks in integration tests
