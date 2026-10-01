# Olympus MVP

Python 3.12 modular monolith: FastAPI control API, scheduler and execution workers, PostgreSQL 16 + pgvector.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker (PostgreSQL locally and Testcontainers in tests)

## Quick start

```bash
cp .env.example .env
make setup
make db-up
make migrate
uv run uvicorn apps.control_api.main:app --reload
curl -fsS localhost:8000/health
curl -fsS localhost:8000/ready
```

## Make targets

| Target | Description |
|--------|-------------|
| `make setup` | Install dependencies and pre-commit hooks |
| `make db-up` / `make db-down` | Start or stop PostgreSQL via Docker Compose |
| `make migrate` | Apply Alembic migrations |
| `make lint` | Ruff + import-linter |
| `make typecheck` | mypy on core and app entrypoints |
| `make check` | lint, typecheck, and deterministic test lanes |

Workers (noop loop until Phase 03):

```bash
uv run python -m apps.scheduler_worker.main --once
uv run python -m apps.execution_worker.main --once
```

## Layout

See `plans/README.md` for the full target repository layout and phase index.

## Tests

```bash
uv run pytest -m "unit or persistence or integration"
```

Persistence and integration tests use Testcontainers (`pgvector/pgvector:pg16`). On macOS, ensure Docker Desktop is running; set `TESTCONTAINERS_RYUK_DISABLED=true` if Ryuk causes issues.
