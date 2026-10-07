.PHONY: setup db-up db-down migrate lint typecheck test-unit test-persistence test-integration test-live test-journey check

setup:
	uv sync --all-groups
	uv run pre-commit install

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
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
	LLM_LIVE_TESTS=1 uv run pytest -m journey --live-required

check: lint typecheck test-unit test-persistence test-integration
