#!/usr/bin/env bash
# Run all of Olympus locally with one command: database, API, both workers and the dashboard.
#
#   make dev          (or ./scripts/dev.sh)
#
# First run sets up .env, the database and a local sign-in token. Ctrl+C stops everything.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${OLYMPUS_API_PORT:-8000}"
UI_PORT="${OLYMPUS_UI_PORT:-3010}"
LOG_DIR="$ROOT/var/olympus/logs"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$*" >&2; }
fail() {
  printf '\033[31m  ✗ %s\033[0m\n' "$*" >&2
  exit 1
}

need() { command -v "$1" >/dev/null 2>&1 || fail "$1 is not installed. $2"; }
port_free() { ! (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

bold "Olympus — starting locally"

need uv "Install it from https://docs.astral.sh/uv/"
need docker "Install Docker and make sure it is running."
need npm "Install Node.js 20 or newer."
docker info >/dev/null 2>&1 || fail "Docker is installed but not running. Start Docker and try again."

if [[ ! -f .env ]]; then
  cp .env.example .env
  info "Created .env from .env.example"
fi
set -a
# shellcheck disable=SC1091
source ./.env
set +a
export OLYMPUS_ENV="${OLYMPUS_ENV:-local}"
if [[ "$OLYMPUS_ENV" != "local" ]]; then
  fail "OLYMPUS_ENV is '$OLYMPUS_ENV' in .env. make dev needs OLYMPUS_ENV=local."
fi
if [[ -z "${OPENAI_API_KEY:-}" && -z "${ANTHROPIC_API_KEY:-}" ]]; then
  warn "No OPENAI_API_KEY or ANTHROPIC_API_KEY in .env: the dashboard will open, but agents"
  warn "cannot run until you add one and restart."
fi

for port in "$API_PORT" "$UI_PORT"; do
  port_free "$port" || fail "Port $port is already in use. Stop whatever uses it, or set \
OLYMPUS_API_PORT / OLYMPUS_UI_PORT."
done

info "Installing Python dependencies (uv sync)…"
uv sync --quiet
if [[ ! -d apps/dashboard/node_modules ]]; then
  info "Installing dashboard dependencies (npm ci)…"
  (cd apps/dashboard && npm ci --no-audit --no-fund --loglevel=error)
fi

# Quiet on success; show the captured output if a step fails.
quiet() {
  local out
  if ! out="$("$@" 2>&1)"; then
    printf '%s\n' "$out" >&2
    return 1
  fi
}

info "Starting the database…"
quiet docker compose up -d postgres --wait || fail "The database did not start (see above)."
quiet make --no-print-directory migrate || fail "Database migration failed (see above)."
info "Database ready and migrated"

TOKEN="$(uv run --quiet python -m apps.control_api.cli.local_token)"
cat >apps/dashboard/.env.local <<EOF
# Written by scripts/dev.sh — local sign-in for this machine. Safe to delete; make dev recreates it.
NEXT_PUBLIC_OLYMPUS_API_URL=http://127.0.0.1:${API_PORT}
NEXT_PUBLIC_OLYMPUS_API_TOKEN=${TOKEN}
EOF
chmod 600 apps/dashboard/.env.local
info "Signed in as the local owner"

mkdir -p "$LOG_DIR"
# Job control puts every service in its own process group, so stopping a group stops the
# service and everything it started (uv → python, npm → next).
set -m
PIDS=()
cleanup() {
  trap - INT TERM EXIT
  echo
  bold "Stopping Olympus…"
  for pid in "${PIDS[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for _ in $(seq 1 10); do
    alive=0
    for pid in "${PIDS[@]}"; do kill -0 -- "-$pid" 2>/dev/null && alive=1; done
    [[ $alive == 0 ]] && break
    sleep 0.5
  done
  for pid in "${PIDS[@]}"; do kill -KILL -- "-$pid" 2>/dev/null || true; done
  info "Stopped. The database keeps running; stop it with: make db-down"
}
trap cleanup INT TERM EXIT

# Each service logs to var/olympus/logs/<name>.log and, prefixed, to this terminal.
run() {
  local name="$1"
  shift
  ("$@" 2>&1 | tee "$LOG_DIR/$name.log" | sed -u "s/^/[$name] /") &
  PIDS+=("$!")
}

run api uv run uvicorn apps.control_api.main:app --host 127.0.0.1 --port "$API_PORT"
run scheduler uv run python -m apps.scheduler_worker.main
run worker uv run python -m apps.execution_worker.main
run ui npm --prefix apps/dashboard run dev -- --port "$UI_PORT" --hostname 127.0.0.1

for _ in $(seq 1 60); do
  curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 && break
  sleep 1
done

echo
bold "Olympus is running → http://127.0.0.1:${UI_PORT}"
info "API http://127.0.0.1:${API_PORT}   ·   logs in var/olympus/logs/   ·   Ctrl+C to stop"
echo
# With job control on, a plain `wait` would return on the first Ctrl+C job notification;
# keep waiting until the services are gone (cleanup runs from the trap).
while kill -0 "${PIDS[0]}" 2>/dev/null; do wait || true; done
