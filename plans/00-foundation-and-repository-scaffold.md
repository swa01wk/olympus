# Phase 00 — Foundation and Repository Scaffold

## 1. Objective

Create the Python 3.12 modular-monolith skeleton prescribed by TECH §4: packaging, configuration, PostgreSQL 16 + pgvector via Docker Compose, the SQLAlchemy 2.x async engine, an Alembic baseline, structured JSON logging with correlation IDs, a FastAPI control-api skeleton, scheduler/execution worker process skeletons, the pytest harness with all markers and Testcontainers, import-boundary enforcement and CI lanes.

This phase exists so every later phase works against one reproducible environment with the trust boundaries (agents ≠ persistence) enforced structurally from the first commit. It creates **no domain entities**.

## 2. Architectural Context

- **Position:** below everything. It provides the process topology from TECH §3.1 (control-api, scheduler-worker, execution-worker, postgres; the dashboard follows in Phase 17).
- **Upstream dependencies:** none.
- **Downstream consumers:** all phases.
- **Lifecycle stages:** none.
- **Relevant invariants:** canonical state lives in PostgreSQL (invariant 36 groundwork). Agent packages cannot import persistence (trust boundary, ARCH §3.2). Mocked LLM output is not journey proof (test-lane separation is established here).

## 3. Current Repository Assessment

Inspection on 2026-10-01: the repository has no commits and contains only the two source `.docx` files.

### Existing
- `Olympus_MVP_Architecture_and_Implementation_Plan_v1.2.docx` — **RETAIN** (reference; do not move or modify).
- `Olympus_MVP_Technical_Implementation_Specification_v1.0.docx` — **RETAIN**.
- `.git` with remote `origin` (unreachable during planning) — **RETAIN**.

### Partial
- None.

### Missing
- Everything in scope below — **ADD**.

### Refactor / Migration Required
- None. If task 00.1 finds remote content, re-assess before proceeding.

| Component | Classification |
|---|---|
| `pyproject.toml`, `uv.lock`, `.python-version` | ADD |
| `core/config`, `core/db`, `core/observability` | ADD |
| `apps/control_api`, `apps/scheduler_worker`, `apps/execution_worker` skeletons | ADD |
| Package skeleton for every `core/*` and `agents/*` directory in `plans/README.md` §4 | ADD |
| Alembic (`alembic.ini`, `migrations/`) | ADD |
| Docker Compose / Dockerfile / Makefile / `.env.example` / `.gitignore` | ADD |
| pytest harness + markers + Testcontainers fixtures | ADD |
| import-linter contracts, ruff, mypy, pre-commit | ADD |
| GitHub Actions CI | ADD |

## 4. Scope

- Packaging with `uv`. Runtime deps for this phase: `fastapi`, `uvicorn[standard]`, `pydantic>=2.7`, `pydantic-settings`, `sqlalchemy[asyncio]>=2.0`, `alembic`, `psycopg[binary,pool]>=3.1`, `pgvector`, `httpx`, `structlog`, `uuid6`. Dev deps: `pytest`, `pytest-asyncio`, `testcontainers[postgres]`, `ruff`, `mypy`, `import-linter`, `pre-commit`.
- `core/config/settings.py` — `OlympusSettings` (pydantic-settings), covering every variable in `plans/README.md` §5.6, with secret fields as `SecretStr`. `OLYMPUS_WORKSPACE_ROOT` (and the optional `OLYMPUS_WORKTREE_ROOT` override) are resolved to absolute paths at startup and validated as writable directories (the default lives under the git-ignored `var/`). They are configuration only: no domain row ever stores them (README §5.9.2, D-16). `docker-compose.yml` mounts the workspace root as one shared volume for control-api and both workers.
- `core/db/` — async engine factory, `async_sessionmaker`, `Base` (DeclarativeBase with naming convention), mixins (`UUIDPkMixin`, `TimestampMixin`), `unit_of_work()` async context manager.
- Alembic configured for async engine; baseline revision `0000_p00_baseline.py` enables the `vector` and `pg_trgm` extensions and creates the `langgraph_runtime` schema (reserved, non-authoritative — see Phase 02).
- `core/observability/logging.py` (structlog JSON) and `core/observability/correlation.py` (contextvar `correlation_id`, `X-Correlation-ID` header in/out).
- `apps/control_api/main.py` — `create_app()`, `GET /health` (process), `GET /ready` (DB `SELECT 1` + Alembic head check).
- `apps/scheduler_worker/main.py` and `apps/execution_worker/main.py` — loops with graceful SIGTERM shutdown, a configurable poll interval and a no-op tick. Logic arrives in Phase 03.
- Empty packages (with `__init__.py`) for the full target layout.
- `tests/conftest.py` — session-scoped PostgreSQL Testcontainer (`pgvector/pgvector:pg16`), Alembic upgrade fixture and a per-test transactional `AsyncSession` fixture with rollback.
- Marker registration and the `tests/plugins/` package placeholder.
- `.github/workflows/ci.yml` — job `deterministic` (lint, typecheck, unit, persistence, integration with a postgres service) and job `live` (`workflow_dispatch` only, requires secrets; populated in Phase 02).
- Root `README.md` (developer onboarding: prerequisites, make targets).

## 5. Out of Scope

- Any domain table, entity, API beyond health/ready, or business logic.
- LLM provider dependencies (Phase 02), LangGraph (Phase 02), the Next.js dashboard (Phase 17) and OpenTelemetry (Phase 18).

### Do Not Change
- The two source `.docx` files.
- Do not choose SQLite or any non-PostgreSQL DB (D-01).

## 6. Domain / Data Model Changes

None beyond the baseline migration:

```python
# migrations/versions/0000_p00_baseline.py
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE SCHEMA IF NOT EXISTS langgraph_runtime")


def downgrade():
    op.execute("DROP SCHEMA IF EXISTS langgraph_runtime CASCADE")
    # extensions left in place intentionally (shared); document in migration docstring
```

Base conventions:

```python
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class UUIDPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid6.uuid7)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

## 7. State / Lifecycle Changes

None.

## 8. API / Contract Changes

| Method | Path | Response |
|---|---|---|
| GET | `/health` | `200 {"status":"ok","version":"<pkg version>"}` |
| GET | `/ready` | `200 {"db":"ok","migrations":"head"}` or `503` with the failing component |

All responses echo `X-Correlation-ID`, generating a UUIDv7 if absent.

## 9. Services / Modules

| Path | Responsibility |
|---|---|
| `pyproject.toml` | deps, `[tool.pytest.ini_options]` markers + `asyncio_mode = "auto"`, ruff, mypy (strict for `core`), import-linter contracts |
| `core/config/settings.py` | `OlympusSettings`, `get_settings()` (lru_cache) |
| `core/db/engine.py`, `session.py`, `base.py`, `uow.py` | async engine/session, Base, unit of work |
| `core/observability/logging.py`, `correlation.py` | JSON logs; correlation contextvar + ASGI middleware |
| `apps/control_api/main.py`, `middleware.py`, `routers/health.py` | app factory + health |
| `apps/scheduler_worker/main.py`, `apps/execution_worker/main.py` | process loops |
| `migrations/env.py`, `alembic.ini` | async Alembic |
| `docker-compose.yml` | `postgres` (pgvector/pgvector:pg16, volume, healthcheck), `control-api` (profile `app`) |
| `Dockerfile` | python:3.12-slim + uv + git |
| `Makefile` | targets listed in `plans/README.md` §6.2 |
| `.importlinter` (or `[tool.importlinter]` in pyproject) | contracts below |
| `tests/conftest.py`, `tests/unit/test_settings.py`, `tests/integration/test_db_and_migrations.py`, `tests/integration/test_health_api.py`, `tests/unit/test_workers_shutdown.py` | harness + smoke tests |

Import-linter contracts:

```
[importlinter:contract:agents-no-persistence]
type = forbidden
source_modules = agents
forbidden_modules = core.db, core.state, core.commands, sqlalchemy
[importlinter:contract:core-no-apps]
type = forbidden
source_modules = core
forbidden_modules = apps
```

## 10. Development Tasks

- [ ] 00.1 Re-attempt `git fetch origin`. If the remote has content, stop and re-run the repository assessment, then update this plan and `STATUS.md`.
- [ ] 00.2 Create `pyproject.toml` (Python `>=3.12,<3.13`), `.python-version`, then run `uv lock`.
- [ ] 00.3 Create `.gitignore` (`.env`, `var/`, `.olympus/`, `__pycache__/`, `.venv/`, `node_modules/`, `*.egg-info`, `.pytest_cache/`).
- [ ] 00.4 Create `.env.example` with every variable from `plans/README.md` §5.6.
- [ ] 00.5 Implement `core/config/settings.py` with validation, including the rejection of `OLYMPUS_ENV=journey` when `LLM_LIVE_TESTS != 1`.
- [ ] 00.6 Implement `core/db/{engine,session,base,uow}.py`.
- [ ] 00.7 Configure Alembic (async `env.py`, `compare_type=True`) and write `0000_p00_baseline.py`.
- [ ] 00.8 Implement JSON logging and correlation middleware. Every log line includes `correlation_id`, `service` and `env`.
- [ ] 00.9 Implement `create_app()` with `/health` and `/ready`.
- [ ] 00.10 Implement worker loop skeletons with SIGTERM/SIGINT graceful stop and `--once` flag for tests.
- [ ] 00.11 Create every package directory listed in `plans/README.md` §4, each with an `__init__.py`.
- [ ] 00.12 Add `docker-compose.yml`, `Dockerfile` and `Makefile`.
- [ ] 00.13 Add import-linter contracts, ruff config, mypy config and `.pre-commit-config.yaml`.
- [ ] 00.14 Add `tests/conftest.py` with the Testcontainer + migration + transactional session fixtures, and register all markers from `plans/README.md` §6.1.
- [ ] 00.15 Write the smoke tests listed in §12.
- [ ] 00.16 Add `.github/workflows/ci.yml` with the `deterministic` and `live` (dispatch-only placeholder) jobs.
- [ ] 00.17 Write the root `README.md` with setup instructions.
- [ ] 00.18 Make the first commit on `main`. Do not force-push.

## 11. LLM-Dependent Tasks

No LLM dependency in this phase.

## 12. Testing Strategy

### Unit Tests
- `test_settings.py`: defaults, env override, SecretStr redaction in `repr`, journey-without-live rejection, and `OLYMPUS_WORKSPACE_ROOT` resolution/validation (a relative value resolves to an absolute path; an unwritable root fails startup).
- `test_workers_shutdown.py`: the `--once` tick returns, and SIGTERM handler sets the stop flag.

### Persistence Tests
- `test_db_and_migrations.py`: `alembic upgrade head` → `downgrade base` → `upgrade head` on the Testcontainer, the `vector` and `pg_trgm` extensions exist, and the `langgraph_runtime` schema exists.

### Integration Tests
- `test_health_api.py`: `/health` 200, `/ready` 200 with DB, `/ready` 503 with a bad DB URL, and correlation header echo/generation.

### Security Tests
- `lint-imports` passes. A deliberately violating temp module (created in the test, then removed) fails the contract.

### Commands
```
make setup && make db-up && make migrate
make lint && make typecheck
uv run pytest -m "unit or persistence or integration"
docker compose --profile app up -d control-api && curl -fsS localhost:8000/ready
```

## 13. Milestone

From a clean clone, `make setup && make db-up && make migrate && make check` succeeds. The control-api answers `/ready` against PostgreSQL 16 + pgvector, workers start and stop gracefully, logs are JSON with correlation IDs, and agent packages are structurally prevented from importing persistence.

## 14. Acceptance Criteria

- [ ] `uv sync` completes from `uv.lock` on Python 3.12.
- [ ] `alembic upgrade head`, `downgrade base` and `upgrade head` succeed against PostgreSQL 16 with `vector` and `pg_trgm` enabled.
- [ ] `GET /ready` returns 200 with DB available and 503 without it.
- [ ] Every HTTP response carries `X-Correlation-ID`, and log lines carry the same `correlation_id`.
- [ ] Both worker processes start, run one tick (`--once`) and exit 0 on SIGTERM.
- [ ] All markers from `plans/README.md` §6.1 are registered, and `pytest --strict-markers` passes.
- [ ] The import-linter contract `agents-no-persistence` is enforced in `make lint`.
- [ ] The CI `deterministic` job definition runs lint, typecheck, unit, persistence and integration with a PostgreSQL service.
- [ ] No domain tables exist yet (only the baseline migration).
- [ ] `OLYMPUS_WORKSPACE_ROOT` is a required settings field, resolved to an absolute writable directory at startup. It is configuration only and is never persisted in a domain row (README D-16, §5.9.2).

## 15. Exit Criteria

- All §14 criteria are checked, and `make check` is green locally and in CI.
- The first commit exists on `main`, and the remote divergence check (00.1) is resolved.
- `STATUS.md` has Phase 00 set to COMPLETE with evidence notes.

## 16. Dependencies

### Depends On
- None.

### Blocks
- 01 and, transitively, all phases.

### Can Run In Parallel With
- None. Everything depends on the scaffold.

## 17. Risks / Implementation Notes

- **R-REMOTE:** unknown remote content (see `plans/README.md` §1).
- **Async Alembic:** use `connection.run_sync(do_run_migrations)` in `env.py`. Do not mix sync engines into application code.
- **Testcontainers on macOS:** requires a Docker daemon. Document the `TESTCONTAINERS_RYUK_DISABLED` workaround if needed.
- **Deferred:** dashboard toolchain (Phase 17) and OTel (Phase 18).

## 18. Deliverables

- Packaging: `pyproject.toml`, `uv.lock`, `.python-version`.
- Code: `core/config`, `core/db`, `core/observability`, `apps/*` skeletons, full package tree.
- Migration: `0000_p00_baseline.py`.
- API: `/health`, `/ready`.
- Config: `.env.example`, `docker-compose.yml`, `Dockerfile`, `Makefile`, `.pre-commit-config.yaml`, import-linter contracts.
- Tests: settings, workers, migrations, health, import-boundary.
- CI: `.github/workflows/ci.yml`.
- Docs: root `README.md`.
