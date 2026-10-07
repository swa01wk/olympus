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
| `make verify-phases` | Phases **00–14**: plan §12 lanes + `make check` + full deterministic pytest tree + **`make test-journey`** |
| `make verify-phases-live` | Same + all `live_llm` tests (`make test-live`); needs API keys in `.env` |
| `./scripts/verify-phases-00-07.sh --phase 08` | Phase 08 only (IC git E2E, traceability, unit/persistence IC tests, deterministic workflow execution) |
| `./scripts/verify-phases-00-07.sh --phase 08 --live` | Phase 08 §12 + **§15 exit**: handoff doc, deterministic + live `tests/workflow/integration` IC precursor (live Forge ×2 → IC READY; needs API keys with `--live`) |
| `make verify-phase-08-exit` | Same as `./scripts/verify-phases-00-07.sh --phase 08 --live` |
| `./scripts/verify-phases-00-07.sh --phase 10` | Phase 10 only (release unit/persistence/integration/git/security, workflow + journey Greenfield → R1, **`make check`**) |
| `make verify-phase-10-exit` | Same as `./scripts/verify-phases-00-07.sh --phase 10` |
| `./scripts/verify-phases-00-07.sh --phase 11` | Phase 11 only (brownfield unit/integration/git/security/workflow; **`make check`** when scoped) |
| `make verify-phase-11-exit` | Same as `./scripts/verify-phases-00-07.sh --phase 11 --live` (includes Scout live LLM) |
| `./scripts/verify-phases-00-07.sh --phase 13` | Phase 13 only (impact unit/integration, persistence, incremental index; **`make check`** when scoped) |
| `make verify-phase-13` | Same as `./scripts/verify-phases-00-07.sh --phase 13` |
| `make verify-phase-13-exit` | Same as `./scripts/verify-phases-00-07.sh --phase 13 --live` (includes live semantic retrieval) |
| `./scripts/verify-phases-00-07.sh --phase 14` | Phase 14 only (ChangeRequest idempotency, interpretation validator, trusted seed; **`make check`** when scoped) |
| `make verify-phase-14` | Same as `./scripts/verify-phases-00-07.sh --phase 14` |
| `make verify-phase-14-exit` | Same as `./scripts/verify-phases-00-07.sh --phase 14 --live` (includes live change interpret + Feature Change journey) |
| `make test-journey` | Phase 10 Greenfield journey test (`tests/journey/test_greenfield_supportdesk.py`) |
| **Phase 16 — OSS integrations** | |
| `make integrations-up` | Gitea, MinIO, CI runner, fault proxy (`deploy/compose.test.yaml`) |
| `make integrations-seed` | Gitea admin + API token → `.env` |
| `make integrations-ready` | `integrations-up` + wait + seed (one shot before live tests) |
| `make test-integrations-p16` | Deterministic §12/§14 (HMAC, sync, reconciliation, connectors, acceptance) |
| `make test-connector-live` | Live compose health + Gitea API (needs `.env` / `GITEA_API_TOKEN`) |
| `make test-journey-issue-tracker` | Live §13: Gitea issue → Feature Change R2 + attach_remote + CI + deploy + issue close |
| `make verify-phase-16` | `./scripts/verify-phases-00-07.sh --phase 16` (deterministic + `test-integrations-p16`) |
| `make verify-phase-16-exit` | Same with `--live`: compose, seed, `test-connector-live`, **`test-journey-issue-tracker`** |
| `make verify-phase-16-live-journey` | Only §13 live journey (`integrations-ready` + `test-journey-issue-tracker`) |
| **Phase 17 — Operator APIs & Orchestrator (backend only; no dashboard)** | |
| `make verify-phase-17` | `./scripts/verify-phases-00-07.sh --phase 17` (alembic **0031**, views/orchestrator pytest) |
| `make verify-phase-17-exit` | Same with `--live`: **`LLM_LIVE_TESTS=1`** → `test_orchestrator_live.py` |
| **Phase 18 — Observability, security & recovery** | |
| `make verify-phase-18` | Security + recovery + observability pytest lane (excludes **`live_llm`**) |
| `make verify-phase-18-live` | **`LLM_LIVE_TESTS=1`**: Scout/Forge prompt-injection live (`tests/security/live/`) + RC-01 placeholder |
| `make verify-phase-18-exit` | **`verify-phase-18`** then **`verify-phase-18-live`** (plan §15 exit) |

### OSS integrations quickstart (Gitea + MinIO)

All services are open source. Use **`git_provider_gitea`** (not GitHub) for remotes, webhooks, and PRs.

```bash
# Deterministic Phase 16 (no LLM, no compose required for most tests)
make test-integrations-p16

# Live stack + token
make integrations-ready
set -a && source .env && source config/integrations/oss-dev.env && set +a
make test-connector-live

# Full §13 journey (live LLM keys + GITEA_API_TOKEN; long-running)
export LLM_LIVE_TESTS=1   # also set MODEL_* / provider API keys
make test-journey-issue-tracker
# or: make verify-phase-16-live-journey

# Scripted sign-off
make verify-phase-16          # deterministic
make verify-phase-16-exit     # + compose + live journey
```

Register a remote repo against local Gitea (HTTPS URL + `credential_ref=secret:gitea-api` after `PUT /secrets/gitea-api` with the token value). Webhook HMAC secrets: create an `integration_sources` row with `auth_kind=HMAC_SHA256` and `secret_ref=secret:…`.

```bash
make integrations-down
```

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

Persistence and integration tests use Testcontainers (`pgvector/pgvector:pg16`). On macOS, ensure Docker Desktop is running; `TESTCONTAINERS_RYUK_DISABLED=true` is set by default in tests and `scripts/verify-phases-00-07.sh`.

If `make migrate` fails with **Can't locate revision** (old local Postgres volume), reset Compose data and re-migrate:

```bash
docker compose down -v && make db-up && make migrate
```

`make db-up` waits for the Compose healthcheck; `make migrate` also runs `pg_isready` so Alembic does not hit a fresh volume before Postgres accepts connections. If you still see **connection closed unexpectedly** on port 5432, something else may be bound to `5432` (not this project's container)—check with `docker compose ps` and `lsof -i :5432`.
