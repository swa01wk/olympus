"""Complete GREENFIELD implementation tasks using SupportDesk R1 fixture tree (no live Forge)."""

from __future__ import annotations

import uuid

from core.commands.context import CommandContext
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import TaskContractStatus, TaskOrigin, TaskStatus, WorkType
from core.domain.executions.models import Execution
from core.domain.repositories.models import Repository
from core.domain.task_contracts.models import TaskContract
from core.domain.tasks.models import Task
from core.execution.worktrees.manager import WorktreeManager
from core.intelligence.code_index.enums import EntityType
from core.intelligence.code_index.parsers.imports import entity_key_for_qn
from core.product_model.models import AcceptanceCriterion
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.code_index_harness import SUPPORTDESK_R1
from tests.fixtures.gateway_harness import seed_gateway_execution
from tests.fixtures.integration_harness import (
    CodeTaskBundle,
    IntegrationFixture,
    commit_files_in_worktree,
)


async def _ensure_execution_worktree(
    session: AsyncSession,
    execution: Execution,
    repository: Repository,
    base_sha: str,
    ctx: CommandContext,
    *,
    project_id: uuid.UUID,
) -> None:
    from core.domain.execution_workspaces.models import ExecutionWorkspace

    existing = (
        await session.execute(
            select(ExecutionWorkspace).where(ExecutionWorkspace.execution_id == execution.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    await WorktreeManager().create(
        session,
        execution,
        repository.id,
        base_sha,
        actor_id=ctx.actor.id,
        correlation_id=ctx.correlation_id,
        project_id=project_id,
    )


def _supportdesk_r2_priority_files() -> dict[str, str]:
    """SupportDesk R1 tree with ticket priority (LOW/MEDIUM/HIGH, default MEDIUM)."""
    files = _supportdesk_files()
    files["app/schemas/ticket.py"] = """from enum import StrEnum

from pydantic import BaseModel


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class TicketPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TicketCreate(BaseModel):
    title: str
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketRead(BaseModel):
    id: int
    title: str
    status: TicketStatus
    priority: TicketPriority
"""
    files["app/models/ticket.py"] = """from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(16), default="MEDIUM")
"""
    files["app/services/ticket_service.py"] = """from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ticket import TicketCreate, TicketStatus


class TicketService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = TicketRepository(session)

    def create(self, payload: TicketCreate) -> Ticket:
        ticket = Ticket(
            title=payload.title,
            status=payload.status.value,
            priority=payload.priority.value,
        )
        return self._repo.add(ticket)

    def update_status(self, ticket_id: int, status: TicketStatus) -> Ticket | None:
        ticket = self._session.get(Ticket, ticket_id)
        if ticket is None:
            return None
        ticket.status = status.value
        return ticket
"""
    files["app/api/tickets.py"] = """from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.schemas.ticket import TicketCreate, TicketPriority, TicketRead, TicketStatus
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=TicketRead, status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> TicketRead:
    service = TicketService(db)
    ticket = service.create(payload)
    return TicketRead(
        id=ticket.id,
        title=ticket.title,
        status=TicketStatus(ticket.status),
        priority=TicketPriority(ticket.priority),
    )
"""
    files["tests/test_tickets_api.py"] = """import app.models.ticket  # noqa: F401
from app.db import Base, engine

Base.metadata.create_all(bind=engine)

from app.main import app
from fastapi.testclient import TestClient


def test_create_ticket() -> None:
    with TestClient(app) as client:
        response = client.post("/tickets", json={"title": "Help", "status": "OPEN"})
        assert response.status_code == 201


def test_create_ticket_default_priority_medium() -> None:
    with TestClient(app) as client:
        response = client.post("/tickets", json={"title": "Priority check"})
        assert response.status_code == 201
        body = response.json()
        assert body["priority"] == "MEDIUM"


def test_create_ticket_explicit_priority() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/tickets",
            json={"title": "Urgent", "priority": "HIGH"},
        )
        assert response.status_code == 201
        assert response.json()["priority"] == "HIGH"


def test_create_ticket_low_priority() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/tickets",
            json={"title": "Low", "priority": "LOW"},
        )
        assert response.status_code == 201
        assert response.json()["priority"] == "LOW"
"""
    files["tests/test_ticket_service.py"] = """import app.models.ticket  # noqa: F401
from app.db import Base, SessionLocal, engine
from app.schemas.ticket import TicketCreate, TicketStatus, TicketPriority
from app.services.ticket_service import TicketService

Base.metadata.create_all(bind=engine)


def test_update_status() -> None:
    db = SessionLocal()
    service = TicketService(db)
    created = service.create(TicketCreate(title="x", status=TicketStatus.OPEN))
    updated = service.update_status(created.id, TicketStatus.CLOSED)
    assert updated is not None
    assert updated.status == "CLOSED"


def test_create_defaults_open() -> None:
    db = SessionLocal()
    service = TicketService(db)
    created = service.create(TicketCreate(title="x"))
    assert created.status == "OPEN"
    assert created.priority == "MEDIUM"
"""
    return files


def _supportdesk_files() -> dict[str, str]:
    out: dict[str, str] = {}
    text_suffixes = {".py", ".toml", ".md", ".yaml", ".yml", ".json", ".ini", ".txt"}
    for path in SUPPORTDESK_R1.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        rel = path.relative_to(SUPPORTDESK_R1).as_posix()
        if rel.startswith(".") or rel == "README.md":
            continue
        if path.suffix.lower() not in text_suffixes and path.name != "Dockerfile":
            continue
        out[rel] = path.read_text(encoding="utf-8")
    return out


async def complete_implementation_tasks_minimal_passing(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project: object,
    repository: Repository,
    cycle: DeliveryCycle,
    base_sha: str,
) -> None:
    """Commit a minimal passing tree within each task contract scope (integration smoke)."""
    from tests.fixtures.assurance_harness import (
        ASSURANCE_HARNESS_PYPROJECT,
        DEFAULT_TEST_PATH,
        DEFAULT_TEST_QN,
        INTEGRATION_SMOKE_TEST_BODY,
        INTEGRATION_SMOKE_TEST_PATH,
    )

    tasks = (
        await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle.id,
                Task.work_type == WorkType.CODE_CHANGE,
                Task.origin == TaskOrigin.IMPLEMENTATION_PLAN,
                Task.status != TaskStatus.COMPLETED,
            )
        )
    ).scalars()
    fixture = IntegrationFixture(
        project=project,  # type: ignore[arg-type]
        repository=repository,
        cycle=cycle,
        base_sha=base_sha,
    )
    minimal = {
        "pyproject.toml": ASSURANCE_HARNESS_PYPROJECT,
        "src/ticket.py": "def create_ticket():\n    return 1\n",
        "app/api/tickets.py": "def create_ticket():\n    return 1\n",
        "app/services/ticket_service.py": "class TicketService:\n    pass\n",
        DEFAULT_TEST_PATH: "def test_ac_assurance():\n    assert True\n",
        "tests/unit/test_ac_assurance_unit.py": "def test_ac_assurance():\n    assert True\n",
        "tests/api/test_tickets.py": "def test_tickets():\n    assert True\n",
        "tests/integration/test_smoke.py": INTEGRATION_SMOKE_TEST_BODY,
        INTEGRATION_SMOKE_TEST_PATH: INTEGRATION_SMOKE_TEST_BODY,
    }
    import fnmatch

    from core.domain.task_contracts.schemas import TaskContractBody

    for task in tasks:
        if task.current_contract_id is None:
            continue
        contract = await session.get(TaskContract, task.current_contract_id)
        if contract is None or contract.status != TaskContractStatus.ISSUED:
            continue
        body = TaskContractBody.model_validate(contract.body)
        scope = body.allowed_scope or ["**"]
        files = {
            rel: content
            for rel, content in minimal.items()
            if any(fnmatch.fnmatch(rel, pattern) for pattern in scope)
        }
        if not files:
            for rel, content in minimal.items():
                if any(fnmatch.fnmatch(rel, pattern) for pattern in scope):
                    files[rel] = content
        assert files, f"no minimal files for scope {scope}"
        bundle_exec = await seed_gateway_execution(
            session,
            repository=repository,
            base_commit=base_sha,
            key_prefix=f"gf-{task.key[:8]}-{repository.project_id.hex[-8:]}",
            existing_task=task,
            existing_contract=contract,
            existing_cycle=cycle,
        )
        await _ensure_execution_worktree(
            session,
            bundle_exec.execution,
            repository,
            base_sha,
            ctx,
            project_id=repository.project_id,
        )
        bundle = CodeTaskBundle(
            fixture=fixture,
            task=task,
            contract=contract,
            execution_bundle=bundle_exec,
        )
        ac_keys: list[str] = []
        if task.implementation_spec_id:
            from core.planning.models import ImplementationSpec

            spec_row = await session.get(ImplementationSpec, task.implementation_spec_id)
            if spec_row and spec_row.feature_spec_id:
                acs = await session.execute(
                    select(AcceptanceCriterion).where(
                        AcceptanceCriterion.feature_spec_id == spec_row.feature_spec_id,
                        AcceptanceCriterion.mandatory.is_(True),
                    )
                )
                ac_keys = [a.lineage_key for a in acs.scalars()]
        test_ref = entity_key_for_qn(EntityType.TEST.value, DEFAULT_TEST_PATH, DEFAULT_TEST_QN)
        ac_mappings = [{"ac_ref": key, "test_ref": test_ref} for key in ac_keys]
        impl_output = {
            "summary": "minimal greenfield impl",
            "changed_files": list(files.keys()),
            "tests_added_or_changed": [k for k in files if k.startswith("tests/")],
            "test_commands_run": ["pytest -q"],
            "principal_symbols": ["create_ticket"],
            "ac_test_mapping": ac_mappings,
            "notes": [],
            "open_questions": [],
        }
        await commit_files_in_worktree(
            session,
            ctx,
            bundle,
            files,
            principal_symbols=["create_ticket"],
            implementation_result=impl_output,
        )


async def complete_implementation_tasks_with_supportdesk_r1(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project: object,
    repository: Repository,
    cycle: DeliveryCycle,
    base_sha: str,
    fixture_files: dict[str, str] | None = None,
) -> None:
    from core.domain.tasks.service import TaskService

    task_svc = TaskService()
    for _ in range(32):
        blocked = list(
            (
                await session.execute(
                    select(Task).where(
                        Task.delivery_cycle_id == cycle.id,
                        Task.work_type == WorkType.CODE_CHANGE,
                        Task.status == TaskStatus.BLOCKED,
                    )
                )
            ).scalars()
        )
        if not blocked:
            break
        for task in blocked:
            await task_svc.on_dependency_completed(session, task.id)

    tasks = (
        await session.execute(
            select(Task).where(
                Task.delivery_cycle_id == cycle.id,
                Task.work_type == WorkType.CODE_CHANGE,
                Task.origin == TaskOrigin.IMPLEMENTATION_PLAN,
                Task.status != TaskStatus.COMPLETED,
            )
        )
    ).scalars()
    all_files = fixture_files if fixture_files is not None else _supportdesk_files()
    import fnmatch

    from core.domain.task_contracts.schemas import TaskContractBody

    fixture = IntegrationFixture(
        project=project,  # type: ignore[arg-type]
        repository=repository,
        cycle=cycle,
        base_sha=base_sha,
    )
    from tests.fixtures.assurance_harness import (
        ASSURANCE_HARNESS_PYPROJECT,
        INTEGRATION_SMOKE_TEST_BODY,
        INTEGRATION_SMOKE_TEST_PATH,
    )

    union_scope: list[str] = []
    task_contracts: list[tuple[Task, TaskContract, TaskContractBody]] = []
    for task in tasks:
        if task.current_contract_id is None:
            continue
        contract = await session.get(TaskContract, task.current_contract_id)
        if contract is None or contract.status != TaskContractStatus.ISSUED:
            continue
        body = TaskContractBody.model_validate(contract.body)
        task_contracts.append((task, contract, body))
        for pattern in body.allowed_scope or ["**"]:
            if pattern not in union_scope:
                union_scope.append(pattern)

    def _files_for_scope(scope: list[str]) -> dict[str, str]:
        picked = {
            rel: content
            for rel, content in all_files.items()
            if any(fnmatch.fnmatch(rel, pattern) for pattern in scope)
        }
        if any(fnmatch.fnmatch("pyproject.toml", p) for p in scope):
            picked.setdefault(
                "pyproject.toml",
                all_files.get("pyproject.toml", ASSURANCE_HARNESS_PYPROJECT),
            )
        if not any(k.startswith("tests/") for k in picked):
            for rel, content in all_files.items():
                if rel.startswith("tests/") and any(
                    fnmatch.fnmatch(rel, pattern) for pattern in scope
                ):
                    picked[rel] = content
                    break
        return picked

    commit_scope = union_scope if union_scope else ["**"]
    union_files = _files_for_scope(commit_scope)

    for task, contract, body in task_contracts:
        scope = body.allowed_scope or ["**"]
        files = {
            rel: content
            for rel, content in union_files.items()
            if any(fnmatch.fnmatch(rel, pattern) for pattern in scope)
        }
        if any(fnmatch.fnmatch(INTEGRATION_SMOKE_TEST_PATH, p) for p in scope):
            files.setdefault(INTEGRATION_SMOKE_TEST_PATH, INTEGRATION_SMOKE_TEST_BODY)
        assert files, f"no fixture files match scope {scope}"
        bundle_exec = await seed_gateway_execution(
            session,
            repository=repository,
            base_commit=base_sha,
            key_prefix=f"gf-{task.key[:8]}-{repository.project_id.hex[-8:]}",
            existing_task=task,
            existing_contract=contract,
            existing_cycle=cycle,
        )
        await _ensure_execution_worktree(
            session,
            bundle_exec.execution,
            repository,
            base_sha,
            ctx,
            project_id=repository.project_id,
        )
        bundle = CodeTaskBundle(
            fixture=fixture,
            task=task,
            contract=contract,
            execution_bundle=bundle_exec,
        )
        ac_keys: list[str] = []
        if task.implementation_spec_id:
            impl = task.implementation_spec_id
            from core.planning.models import ImplementationSpec

            spec_row = await session.get(ImplementationSpec, impl)
            if spec_row and spec_row.feature_spec_id:
                acs = await session.execute(
                    select(AcceptanceCriterion).where(
                        AcceptanceCriterion.feature_spec_id == spec_row.feature_spec_id,
                        AcceptanceCriterion.mandatory.is_(True),
                    )
                )
                ac_keys = [a.lineage_key for a in acs.scalars()]
        test_candidates = [
            ("tests/test_tickets_api.py", "tests.test_tickets_api.test_create_ticket"),
            ("tests/test_ticket_service.py", "tests.test_ticket_service.test_update_status"),
            ("tests/test_tickets_api.py", "tests.test_tickets_api.test_list_tickets"),
        ]
        default_path, default_qn = test_candidates[0]
        for tp, tq in test_candidates:
            if tp in files:
                default_path, default_qn = tp, tq
                break

        ac_mappings = []
        for ac_key in ac_keys:
            test_path = default_path
            test_qn = default_qn
            if "PRIORITY" in ac_key and ac_key.endswith("-003"):
                test_path = "tests/test_tickets_api.py"
                test_qn = "tests.test_tickets_api.test_create_ticket_low_priority"
            elif "PRIORITY" in ac_key:
                test_path = "tests/test_tickets_api.py"
                test_qn = "tests.test_tickets_api.test_create_ticket_explicit_priority"
            elif ac_key == "AC-2" and "tests/test_ticket_service.py" in files:
                test_path = "tests/test_ticket_service.py"
                test_qn = "tests.test_ticket_service.test_update_status"
            elif ac_key == "AC-3" and "tests/test_tickets_api.py" in files:
                test_path = "tests/test_tickets_api.py"
                test_qn = "tests.test_tickets_api.test_list_tickets"
            ac_mappings.append(
                {
                    "ac_ref": ac_key,
                    "test_ref": entity_key_for_qn(EntityType.TEST.value, test_path, test_qn),
                }
            )
        impl_output = {
            "summary": "supportdesk r1 fixture",
            "changed_files": list(files.keys()),
            "tests_added_or_changed": [p for p in files if p.startswith("tests/")],
            "test_commands_run": ["pytest -q"],
            "principal_symbols": ["create_ticket"],
            "ac_test_mapping": ac_mappings,
            "notes": [],
            "open_questions": [],
        }
        await commit_files_in_worktree(
            session,
            ctx,
            bundle,
            files,
            principal_symbols=["create_ticket"],
            implementation_result=impl_output,
        )


async def complete_feature_change_implementation_tasks(
    session: AsyncSession,
    ctx: CommandContext,
    *,
    project: object,
    repository: Repository,
    cycle: DeliveryCycle,
    base_sha: str,
) -> None:
    """Finish stuck CODE_CHANGE tasks with the ticket-priority delta (live Forge fallback)."""
    await complete_implementation_tasks_with_supportdesk_r1(
        session,
        ctx,
        project=project,
        repository=repository,
        cycle=cycle,
        base_sha=base_sha,
        fixture_files=_supportdesk_r2_priority_files(),
    )
