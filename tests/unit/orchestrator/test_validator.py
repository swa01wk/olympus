import uuid

import pytest
from agents.orchestrator.schemas import (
    ClarificationAnswerDraft,
    OrchestratorTurn,
    ProposedCommand,
    RevisionNoteDraft,
)
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind, ActorRole
from core.orchestrator.validator import OrchestratorValidationError, validate_turn


def test_unknown_command_rejected() -> None:
    actor = Actor(kind=ActorKind.HUMAN, name="op", roles=[ActorRole.OPERATOR.value])
    turn = OrchestratorTurn(
        intent="PROPOSE_COMMAND",
        message="x",
        proposed_command=ProposedCommand(
            command="not_a_real_command",
            target_ref=str(uuid.uuid4()),
            args={},
            rationale="test",
        ),
    )
    with pytest.raises(OrchestratorValidationError):
        validate_turn(turn, actor=actor)


def test_clarification_draft_required() -> None:
    actor = Actor(kind=ActorKind.HUMAN, name="cl-op", roles=[ActorRole.OPERATOR.value])
    turn = OrchestratorTurn(intent="ANSWER_CLARIFICATION", message="answering")
    with pytest.raises(OrchestratorValidationError, match="CLARIFICATION_DRAFT_REQUIRED"):
        validate_turn(turn, actor=actor)


def test_unknown_clarification_rejected_when_ids_provided() -> None:
    actor = Actor(kind=ActorKind.HUMAN, name="cl-known", roles=[ActorRole.OPERATOR.value])
    turn = OrchestratorTurn(
        intent="ANSWER_CLARIFICATION",
        message="answering",
        clarification_answer_draft=ClarificationAnswerDraft(
            clarification_id=str(uuid.uuid4()),
            answer="409",
        ),
    )
    with pytest.raises(OrchestratorValidationError, match="UNKNOWN_CLARIFICATION"):
        validate_turn(turn, actor=actor, open_clarification_ids=set())


def test_known_open_clarification_accepted() -> None:
    actor = Actor(kind=ActorKind.HUMAN, name="cl-ok", roles=[ActorRole.OPERATOR.value])
    cid = str(uuid.uuid4())
    turn = OrchestratorTurn(
        intent="ANSWER_CLARIFICATION",
        message="answering",
        clarification_answer_draft=ClarificationAnswerDraft(
            clarification_id=cid,
            answer="closed tickets return 409",
        ),
    )
    assert validate_turn(turn, actor=actor, open_clarification_ids={cid}).intent == (
        "ANSWER_CLARIFICATION"
    )


def test_revision_note_draft_requires_pending_approval() -> None:
    actor = Actor(kind=ActorKind.HUMAN, name="rev", roles=[ActorRole.OPERATOR.value])
    aid = str(uuid.uuid4())
    turn = OrchestratorTurn(
        intent="REVISION_NOTE_DRAFT",
        message="note",
        revision_note_draft=RevisionNoteDraft(approval_id=aid, note="fix guard"),
    )
    with pytest.raises(OrchestratorValidationError, match="UNKNOWN_APPROVAL"):
        validate_turn(turn, actor=actor, pending_approval_ids=set())
    assert (
        validate_turn(turn, actor=actor, pending_approval_ids={aid}).intent == "REVISION_NOTE_DRAFT"
    )


def test_approval_decide_blocked() -> None:
    actor = Actor(
        kind=ActorKind.HUMAN,
        name="ap",
        roles=[ActorRole.OPERATOR.value, ActorRole.APPROVER.value],
    )
    turn = OrchestratorTurn(
        intent="PROPOSE_COMMAND",
        message="approve",
        proposed_command=ProposedCommand(
            command="approval.decide",
            target_ref=str(uuid.uuid4()),
            args={"decision": "APPROVED"},
            rationale="test",
        ),
    )
    with pytest.raises(OrchestratorValidationError):
        validate_turn(turn, actor=actor)
