#!/usr/bin/env bash
# Phase 19 MVP environment bootstrap (plan §4.1).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.yml -f deploy/compose.test.yaml -f deploy/compose.demo.yaml)
PROFILES=(--profile integrations --profile demo)

if [[ "${MVP_OBSERVABILITY:-0}" == "1" ]]; then
  COMPOSE+=(-f deploy/compose.observability.yaml --profile observability)
fi

log() { echo "[mvp-bootstrap] $*" >&2; }

log "Removing demo volumes (postgres/workspace/storage)..."
"${COMPOSE[@]}" down -v 2>/dev/null || true

log "Starting stack..."
"${COMPOSE[@]}" "${PROFILES[@]}" up -d --wait

log "Migrating database..."
make migrate

log "Seeding actors (lead + viewer)..."
LEAD_TOKEN="$(uv run python -m apps.control_api.cli.seed_actor --name lead --roles OPERATOR,APPROVER)"
VIEWER_TOKEN="$(uv run python -m apps.control_api.cli.seed_actor --name viewer --roles VIEWER)"
log "Export OLYMPUS_HUMAN_TOKEN / OLYMPUS_VIEWER_TOKEN from bootstrap output."

log "Gitea token + org/repo/webhook..."
"${ROOT}/scripts/integrations-seed.sh" --write-env || true
# Org/repo/webhook registration is completed via Olympus connector APIs during demo driver stage A.

log "Preflight..."
set -a
[[ -f .env ]] && source ./.env
export OLYMPUS_ENV=journey
export LLM_LIVE_TESTS=1
export OLYMPUS_HUMAN_TOKEN="${LEAD_TOKEN}"
export OLYMPUS_VIEWER_TOKEN="${VIEWER_TOKEN}"
set +a
uv run python scripts/demo/preflight.py

printf '%s\n' "$LEAD_TOKEN"
printf '%s\n' "$VIEWER_TOKEN"
