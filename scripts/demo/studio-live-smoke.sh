#!/usr/bin/env bash
# Run Studio @live Playwright (greenfield + RL2) against Docker API + workers tuned for local dev.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.yml -f deploy/compose.demo.yaml -f deploy/compose.studio-live.yaml)

log() { echo "[studio-live-smoke] $*" >&2; }

log "Freeing ports 3010 / stale Playwright…"
pkill -f "playwright test.*studio-" 2>/dev/null || true
lsof -ti :3010 | xargs kill -9 2>/dev/null || true
# Turbopack dev cache can corrupt and panic on first request; clean slate for smoke runs.
rm -rf apps/dashboard/.next

if [[ ! -f "${ROOT}/.env" ]]; then
  log "ERROR: ${ROOT}/.env is missing. Docker workers need live LLM API keys (see .env.example)."
  exit 1
fi

log "Starting postgres + API + workers (studio-live overlay)…"
"${COMPOSE[@]}" --profile demo up -d --build postgres control-api scheduler-worker execution-worker

log "Waiting for control API…"
api_ready=false
for i in $(seq 1 60); do
  if curl -fsS --max-time 2 -o /dev/null http://127.0.0.1:8000/health 2>/dev/null; then
    api_ready=true
    break
  fi
  sleep 1
done
if [[ "$api_ready" != true ]]; then
  log "Control API not healthy on :8000 after 60s"
  exit 1
fi

log "Migrating…"
make migrate

log "Seeding tokens…"
SUFFIX="$(date +%s | tail -c 6)"
OP_TOKEN="$(uv run python -m apps.control_api.cli.seed_actor --name "studio-op-${SUFFIX}" --roles OPERATOR)"
AP_TOKEN="$(uv run python -m apps.control_api.cli.seed_actor --name "studio-ap-${SUFFIX}" --roles OPERATOR,APPROVER)"
printf '%s' "$OP_TOKEN" > /tmp/olympus-op.token
printf '%s' "$AP_TOKEN" > /tmp/olympus-ap.token

if [[ "${STUDIO_LIVE_SKIP_SANITY:-}" == "1" ]]; then
  log "Skipping LLM sanity (STUDIO_LIVE_SKIP_SANITY=1)"
else
  log "Sanity: live revision test (LLM + workers; often 15–90s, output below)…"
  LLM_LIVE_TESTS=1 uv run pytest tests/integration/live_llm/test_revision_loop_live.py -v --tb=short
fi

export OLYMPUS_OPERATOR_TOKEN="$OP_TOKEN"
export OLYMPUS_APPROVER_TOKEN="$AP_TOKEN"
export NEXT_PUBLIC_OLYMPUS_API_URL=http://127.0.0.1:8000

log "Starting dashboard on :3010 (do not run a separate npm run dev; this script owns :3010)…"
cd apps/dashboard
: > /tmp/dashboard-3010.log
# Webpack dev is slower to start but avoids Turbopack persistence panics during long @live runs.
nohup npm run dev -- --port 3010 -H 127.0.0.1 --webpack >> /tmp/dashboard-3010.log 2>&1 &
dashboard_pid=$!

dashboard_ready=false
# First webpack compile can take 30–90s; allow long per-request timeouts while polling.
for i in $(seq 1 45); do
  if ! kill -0 "$dashboard_pid" 2>/dev/null; then
    log "Dashboard process exited early. Tail of /tmp/dashboard-3010.log:"
    tail -n 40 /tmp/dashboard-3010.log >&2 || true
    exit 1
  fi
  if curl -fsS --max-time 90 -o /dev/null http://127.0.0.1:3010/ 2>/dev/null; then
    dashboard_ready=true
    break
  fi
  if (( i == 1 || i % 5 == 0 )); then
    log "Waiting for dashboard on :3010 (webpack may compile on first hit)… (${i}/45)"
  fi
  sleep 2
done
if [[ "$dashboard_ready" != true ]]; then
  log "Dashboard did not respond on :3010. Tail of /tmp/dashboard-3010.log:"
  tail -n 40 /tmp/dashboard-3010.log >&2 || true
  exit 1
fi
log "Dashboard ready on :3010 (Playwright will reuse it)"

SPEC="${1:-tests/e2e/studio-rl2.spec.ts}"
log "Playwright: $SPEC"
npm run test:e2e:live -- "$SPEC"
