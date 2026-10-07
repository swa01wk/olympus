COMPOSE := docker compose
COMPOSE_INTEGRATIONS := $(COMPOSE) -f docker-compose.yml -f deploy/compose.test.yaml

.PHONY: setup db-up db-down wait-postgres migrate lint typecheck test-unit test-persistence test-integration test-security test-git test-live test-journey check verify-phases verify-phases-live verify-phase-08-exit verify-phase-10-exit verify-phase-11-exit verify-phase-13 verify-phase-13-exit verify-phase-14 verify-phase-14-exit verify-phase-15 verify-phase-15-exit integrations-up integrations-down integrations-wait integrations-seed integrations-ready test-connector test-integrations-p16 test-connector-live test-journey-issue-tracker verify-phase-16 verify-phase-16-exit verify-phase-16-live-journey verify-phase-17 verify-phase-17-exit mvp-env mvp-demo mvp-demo-chaos mvp-acceptance

COMPOSE_MVP := $(COMPOSE) -f deploy/compose.demo.yaml

setup:
	uv sync --all-groups
	uv run pre-commit install

db-up:
	docker compose up -d postgres --wait

db-down:
	docker compose down

# Fresh volumes need a few seconds after the container is up; pg_isready avoids racey migrate.
wait-postgres:
	@for i in $$(seq 1 30); do \
		docker compose exec -T postgres pg_isready -U olympus -d olympus >/dev/null 2>&1 && exit 0; \
		sleep 1; \
	done; \
	echo "Postgres not ready after 30s (is 'docker compose up -d postgres' running?)" >&2; \
	exit 1

migrate: wait-postgres
	uv run alembic upgrade head

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run lint-imports

typecheck:
	uv run mypy core apps/control_api apps/scheduler_worker apps/execution_worker

test-unit:
	uv run pytest -m unit

test-persistence:
	uv run pytest -m persistence

test-integration:
	uv run pytest -m "integration and not live_llm"

test-live:
	LLM_LIVE_TESTS=1 uv run pytest -m live_llm --live-required

test-journey:
	uv run pytest -m journey

test-security:
	uv run pytest -m security

test-recovery:
	uv run pytest -m recovery

test-git:
	uv run pytest -m git

# Phase 16 — external integrations (plan §12)
integrations-up:
	$(COMPOSE_INTEGRATIONS) --profile integrations up -d --wait

integrations-down:
	$(COMPOSE_INTEGRATIONS) --profile integrations down

integrations-seed:
	@./scripts/integrations-seed.sh --write-env
	@echo "GITEA_API_TOKEN written to .env (re-run seed anytime; replaces token named in GITEA_TOKEN_NAME)"

integrations-ready: integrations-up integrations-wait integrations-seed

integrations-wait:
	@for i in $$(seq 1 60); do \
		curl -sf http://127.0.0.1:3000/api/v1/version >/dev/null 2>&1 && \
		curl -sf http://127.0.0.1:8090/health >/dev/null 2>&1 && \
		curl -sf http://127.0.0.1:9099/health >/dev/null 2>&1 && exit 0; \
		sleep 2; \
	done; \
	echo "Integration services not ready (run: make integrations-up)" >&2; \
	exit 1

test-connector:
	uv run pytest -m connector tests/connector

test-integrations-p16:
	@set -a; [ -f .env ] && . ./.env; set +a; \
	uv run pytest -m "connector or integration" tests/connector tests/integration/integrations tests/unit/integrations/test_hmac_auth.py

test-connector-live: integrations-wait
	@set -a; [ -f .env ] && . ./.env; set +a; \
	OLYMPUS_GITEA_URL=http://127.0.0.1:3000 \
	OLYMPUS_CI_RUNNER_URL=http://127.0.0.1:8090 \
	OLYMPUS_FAULT_PROXY_URL=http://127.0.0.1:9099 \
	OLYMPUS_MINIO_URL=http://127.0.0.1:9000 \
	uv run pytest -m connector_live tests/connector -v

test-journey-issue-tracker: integrations-wait
	@set -a; [ -f .env ] && . ./.env; \
	[ -f config/integrations/oss-dev.env ] && . ./config/integrations/oss-dev.env; set +a; \
	export OLYMPUS_SECRET_KEY="$${OLYMPUS_SECRET_KEY:-journey-live-p16}"; \
	LLM_LIVE_TESTS=1 uv run pytest -m journey --live-required tests/journey/test_feature_change_via_issue_tracker.py -s

# Full Phase 16 §13 live path only (compose + seed + journey; requires live LLM API keys).
verify-phase-16-live-journey: integrations-ready
	@$(MAKE) test-journey-issue-tracker

check: lint typecheck test-unit test-persistence test-integration test-security test-git

verify-phases:
	@./scripts/verify-phases-00-07.sh

verify-phase-08-exit:
	@./scripts/verify-phases-00-07.sh --phase 08 --live

verify-phase-10-exit:
	@./scripts/verify-phases-00-07.sh --phase 10

verify-phase-11-exit:
	@./scripts/verify-phases-00-07.sh --phase 11 --live

verify-phase-13:
	@./scripts/verify-phases-00-07.sh --phase 13

verify-phase-13-exit:
	@./scripts/verify-phases-00-07.sh --phase 13 --live

verify-phase-14:
	@./scripts/verify-phases-00-07.sh --phase 14

verify-phase-14-exit:
	@./scripts/verify-phases-00-07.sh --phase 14 --live

verify-phase-15:
	@./scripts/verify-phases-00-07.sh --phase 15

verify-phase-15-exit:
	@./scripts/verify-phases-00-07.sh --phase 15 --live

verify-phase-16:
	@./scripts/verify-phases-00-07.sh --phase 16

verify-phase-16-exit:
	@./scripts/verify-phases-00-07.sh --phase 16 --live

verify-phase-17:
	@./scripts/verify-phases-00-07.sh --phase 17

verify-phase-17-exit:
	@./scripts/verify-phases-00-07.sh --phase 17 --live

verify-phase-18:
	uv run pytest -m "security or recovery" tests/security tests/recovery tests/integration/observability tests/persistence/test_audit_chain.py tests/persistence/test_llm_retention.py tests/persistence/test_model_call_observability.py tests/integration/test_ready_sandbox.py -m "not live_llm"

verify-phase-18-live:
	LLM_LIVE_TESTS=1 uv run pytest -m live_llm --live-required tests/security/live tests/recovery/test_rc01_forge_kill_live.py

verify-phase-18-exit: verify-phase-18
	$(MAKE) verify-phase-18-live

verify-phases-live:
	@./scripts/verify-phases-00-07.sh --live

# Phase 19 — chained four-journey MVP acceptance
mvp-env:
	@./scripts/demo/bootstrap.sh

mvp-demo: mvp-env
	@set -a; [ -f .env ] && . ./.env; set +a; \
	export OLYMPUS_ENV=journey LLM_LIVE_TESTS=1; \
	RUN_ID=$$(uuidgen | tr '[:upper:]' '[:lower:]'); \
	uv run python scripts/demo/run_mvp.py --report var/olympus/reports; \
	mkdir -p var/olympus/reports; \
	LLM_LIVE_TESTS=1 uv run pytest -m journey --live-required tests/journey/test_mvp_chained_supportdesk.py -s --junitxml=var/olympus/reports/junit-chained.xml; \
	uv run python scripts/acceptance/evaluate_mvp.py --project SUPPORTDESK --run-id "$$RUN_ID" --out var/olympus/reports; \
	uv run python scripts/acceptance/check_matrix.py --matrix tests/acceptance/matrix.yaml --junit 'var/olympus/reports/*.xml'

mvp-demo-chaos: mvp-env
	@set -a; [ -f .env ] && . ./.env; set +a; \
	export OLYMPUS_ENV=journey LLM_LIVE_TESTS=1 MVP_CHAOS=1 MVP_CHAOS_ISSUE_CLOSE_FAULT=timeout_after_forward; \
	RUN_ID=$$(uuidgen | tr '[:upper:]' '[:lower:]'); \
	uv run python scripts/demo/run_mvp.py --chaos --report var/olympus/reports; \
	LLM_LIVE_TESTS=1 MVP_CHAOS=1 uv run pytest -m journey --live-required tests/journey/test_mvp_chained_supportdesk.py -s --junitxml=var/olympus/reports/junit-chained-chaos.xml; \
	uv run python scripts/acceptance/evaluate_mvp.py --project SUPPORTDESK --run-id "$$RUN_ID" --out var/olympus/reports --chaos; \
	uv run python scripts/acceptance/check_matrix.py --matrix tests/acceptance/matrix.yaml --junit 'var/olympus/reports/*.xml'

mvp-acceptance:
	@$(MAKE) mvp-demo
	@$(MAKE) mvp-env
	@$(MAKE) mvp-demo-chaos
