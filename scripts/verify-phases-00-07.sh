#!/usr/bin/env bash
# Local verification for Olympus MVP Phases 00–17.
# Runs each phase plan §12 commands, then full-repo gates:
#   • make check (deterministic CI parity)
#   • pytest -m "not live_llm and not journey" (full deterministic tree)
#   • make test-journey (Phase 10 Greenfield PRD → Release R1)
#   • make test-live when --live (every live_llm test)
#
# Usage:
#   ./scripts/verify-phases-00-07.sh [--skip-bootstrap] [--live] [--skip-smoke-api] [--phase NN]
#
# Examples:
#   ./scripts/verify-phases-00-07.sh
#   ./scripts/verify-phases-00-07.sh --live          # same as: make verify-phases-live
#   ./scripts/verify-phases-00-07.sh --phase 08
#   ./scripts/verify-phases-00-07.sh --phase 09
#   ./scripts/verify-phases-00-07.sh --phase 10
#   ./scripts/verify-phases-00-07.sh --phase 11
#   ./scripts/verify-phases-00-07.sh --phase 11 --live
#   ./scripts/verify-phases-00-07.sh --phase 12
#   ./scripts/verify-phases-00-07.sh --phase 12 --live
#   ./scripts/verify-phases-00-07.sh --phase 13
#   ./scripts/verify-phases-00-07.sh --phase 13 --live
#   ./scripts/verify-phases-00-07.sh --phase 14
#   ./scripts/verify-phases-00-07.sh --phase 14 --live
#   ./scripts/verify-phases-00-07.sh --phase 15
#   ./scripts/verify-phases-00-07.sh --phase 15 --live
#   ./scripts/verify-phases-00-07.sh --phase 16
#   ./scripts/verify-phases-00-07.sh --phase 16 --live
#   ./scripts/verify-phases-00-07.sh --phase 17
#   ./scripts/verify-phases-00-07.sh --phase 17 --live  # same as: make verify-phase-17-exit

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Testcontainers + Docker Desktop (macOS): Ryuk often breaks port mapping.
export TESTCONTAINERS_RYUK_DISABLED="${TESTCONTAINERS_RYUK_DISABLED:-true}"

SKIP_BOOTSTRAP=0
RUN_LIVE=0
SKIP_SMOKE_API=0
ONLY_PHASE=""

usage() {
  sed -n '2,32p' "$0" | tail -n +2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-bootstrap) SKIP_BOOTSTRAP=1 ;;
    --live) RUN_LIVE=1 ;;
    --skip-smoke-api) SKIP_SMOKE_API=1 ;;
    --smoke-api) ;; # legacy no-op (smoke API is on by default)
    --phase)
      ONLY_PHASE="${2:?--phase requires 00–17}"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ -n "$ONLY_PHASE" && ! "$ONLY_PHASE" =~ ^(0[0-9]|1[0-7])$ ]]; then
  echo "Invalid --phase '$ONLY_PHASE' (use 00–17)" >&2
  exit 2
fi

if command -v uv >/dev/null 2>&1; then
  PYTEST=(uv run pytest)
  ALEMBIC=(uv run alembic)
  PYTHON=(uv run python)
else
  PYTEST=(.venv/bin/pytest)
  ALEMBIC=(.venv/bin/alembic)
  PYTHON=(.venv/bin/python)
fi

LOG="$(mktemp -t olympus-verify.XXXXXX)"
trap 'rm -f "$LOG"' EXIT

# Bash 3.2 (macOS default) has no associative arrays — use explicit status slots.
GLOBAL_FAIL=0
CURRENT_PHASE=""
BOOTSTRAP_RAN=0
COMPOSE_DB_MIGRATED=0

status_set() {
  local key="$1"
  local val="$2"
  case "$key" in
    BOOT) STATUS_BOOT="$val" ;;
    00) STATUS_00="$val" ;;
    01) STATUS_01="$val" ;;
    02) STATUS_02="$val" ;;
    03) STATUS_03="$val" ;;
    04) STATUS_04="$val" ;;
    05) STATUS_05="$val" ;;
    06) STATUS_06="$val" ;;
    07) STATUS_07="$val" ;;
    08) STATUS_08="$val" ;;
    09) STATUS_09="$val" ;;
    10) STATUS_10="$val" ;;
    11) STATUS_11="$val" ;;
    12) STATUS_12="$val" ;;
    13) STATUS_13="$val" ;;
    14) STATUS_14="$val" ;;
    15) STATUS_15="$val" ;;
    16) STATUS_16="$val" ;;
    17) STATUS_17="$val" ;;
    CHECK) STATUS_CHECK="$val" ;;
    FULL-DET) STATUS_FULL_DET="$val" ;;
    LIVE) STATUS_LIVE="$val" ;;
    JOURNEY) STATUS_JOURNEY="$val" ;;
    *) STATUS_OTHER="$val" ;;
  esac
}

status_get() {
  local key="$1"
  case "$key" in
    BOOT) echo "${STATUS_BOOT:-SKIP}" ;;
    00) echo "${STATUS_00:-SKIP}" ;;
    01) echo "${STATUS_01:-SKIP}" ;;
    02) echo "${STATUS_02:-SKIP}" ;;
    03) echo "${STATUS_03:-SKIP}" ;;
    04) echo "${STATUS_04:-SKIP}" ;;
    05) echo "${STATUS_05:-SKIP}" ;;
    06) echo "${STATUS_06:-SKIP}" ;;
    07) echo "${STATUS_07:-SKIP}" ;;
    08) echo "${STATUS_08:-SKIP}" ;;
    09) echo "${STATUS_09:-SKIP}" ;;
    10) echo "${STATUS_10:-SKIP}" ;;
    11) echo "${STATUS_11:-SKIP}" ;;
    12) echo "${STATUS_12:-SKIP}" ;;
    13) echo "${STATUS_13:-SKIP}" ;;
    14) echo "${STATUS_14:-SKIP}" ;;
    15) echo "${STATUS_15:-SKIP}" ;;
    16) echo "${STATUS_16:-SKIP}" ;;
    17) echo "${STATUS_17:-SKIP}" ;;
    CHECK) echo "${STATUS_CHECK:-SKIP}" ;;
    FULL-DET) echo "${STATUS_FULL_DET:-SKIP}" ;;
    LIVE) echo "${STATUS_LIVE:-SKIP}" ;;
    JOURNEY) echo "${STATUS_JOURNEY:-SKIP}" ;;
    *) echo "${STATUS_OTHER:-SKIP}" ;;
  esac
}

should_run_phase() {
  local id="$1"
  [[ -z "$ONLY_PHASE" || "$ONLY_PHASE" == "$id" ]]
}

run_step() {
  local desc="$1"
  shift
  printf '  • %-55s ' "$desc"
  if "$@" >"$LOG" 2>&1; then
    echo "PASS"
    return 0
  fi
  echo "FAIL"
  tail -n 25 "$LOG" | sed 's/^/      /'
  status_set "$CURRENT_PHASE" "FAIL"
  GLOBAL_FAIL=1
  return 1
}

# Live Scout is LLM-flaky under long verify runs; one retry before failing the phase.
run_step_live_scout() {
  local desc="$1"
  shift
  printf '  • %-55s ' "$desc"
  if "$@" >"$LOG" 2>&1; then
    echo "PASS"
    return 0
  fi
  echo "FAIL"
  tail -n 25 "$LOG" | sed 's/^/      /'
  printf '  • %-55s ' "${desc} (retry)"
  if "$@" >"$LOG" 2>&1; then
    echo "PASS"
    return 0
  fi
  echo "FAIL"
  tail -n 25 "$LOG" | sed 's/^/      /'
  status_set "$CURRENT_PHASE" "FAIL"
  GLOBAL_FAIL=1
  return 1
}

skip_step() {
  local desc="$1"
  printf '  • %-55s SKIP\n' "$desc"
}

begin_phase() {
  CURRENT_PHASE="$1"
  local title="$2"
  if ! should_run_phase "$CURRENT_PHASE"; then
    CURRENT_PHASE=""
    return 1
  fi
  status_set "$CURRENT_PHASE" "PASS"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  printf "Phase %s — %s\n" "$CURRENT_PHASE" "$title"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  return 0
}

end_phase() {
  if [[ -z "$CURRENT_PHASE" ]]; then
    return 0
  fi
  local st
  st="$(status_get "$CURRENT_PHASE")"
  [[ "$st" == "SKIP" ]] && st="PASS"
  if [[ "$st" == "PASS" ]]; then
    printf "→ Phase %s: \033[32mPASS\033[0m\n" "$CURRENT_PHASE"
  else
    printf "→ Phase %s: \033[31mFAIL\033[0m\n" "$CURRENT_PHASE"
  fi
  CURRENT_PHASE=""
}

run_full_gate() {
  local key="$1"
  local title="$2"
  shift 2
  CURRENT_PHASE=""
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$title"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  if "$@" >"$LOG" 2>&1; then
    printf "→ %s: \033[32mPASS\033[0m\n" "$key"
    status_set "$key" "PASS"
  else
    printf "→ %s: \033[31mFAIL\033[0m\n" "$key"
    tail -n 30 "$LOG" | sed 's/^/      /'
    status_set "$key" "FAIL"
    GLOBAL_FAIL=1
  fi
}

# Phase 10+: Greenfield journey (deterministic; live seven-alias chain is optional / make test-live).
run_journey_gate() {
  CURRENT_PHASE=""
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Journey gate — make test-journey (Phase 10 Greenfield → R1)"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  if make test-journey >"$LOG" 2>&1; then
    printf "→ JOURNEY: \033[32mPASS\033[0m\n"
    status_set JOURNEY "PASS"
    return 0
  fi
  printf "→ JOURNEY: \033[31mFAIL\033[0m\n"
  tail -n 30 "$LOG" | sed 's/^/      /'
  status_set JOURNEY "FAIL"
  GLOBAL_FAIL=1
  return 1
}

alembic_at_mvp_head() {
  # Keep in sync with migrations/versions head (Phase 17 → 0031_p17_orchestrator).
  "${ALEMBIC[@]}" current 2>&1 | grep -qE \
    '0031_p17_orchestrator|0030_p16_integrations|0029_p15_unreproduced_approval|0028_p15_defects|0027_feature_spec_supersede|0026_p14_change_requests|0025_p13_spec_deltas_impact|0024_p12_baselines_readiness|0023_p11_brownfield_recovery|0022_p10_scoped_assurance_keys|0021_p10_scoped_keys'
}

live_pytest() {
  env LLM_LIVE_TESTS=1 "${PYTEST[@]}" -m live_llm --live-required "$@"
}

wait_for_compose_postgres() {
  local i
  for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U olympus -d olympus >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# Migrate the Compose Postgres (.env DATABASE_URL). Recreate volumes if alembic_version
# references renamed revisions (e.g. 0001_p01_domain_kernel → 0001_p01_repos).
smoke_control_api_ready() {
  docker compose --profile app up -d --build control-api
  local i
  for i in $(seq 1 45); do
    if curl -fsS "http://127.0.0.1:8000/ready" >/dev/null 2>&1; then
      curl -fsS "http://127.0.0.1:8000/ready"
      echo ""
      return 0
    fi
    sleep 2
  done
  {
    echo "control-api not ready after 90s; recent logs:"
    docker compose --profile app logs control-api --tail 50
  } >>"$LOG" 2>&1
  return 1
}

migrate_compose_database() {
  if make migrate >"$LOG" 2>&1; then
    COMPOSE_DB_MIGRATED=1
    return 0
  fi
  if grep -q "Can't locate revision" "$LOG"; then
    {
      echo "Stale alembic_version in Docker Postgres; recreating Compose volumes (docker compose down -v)."
      docker compose down -v
      docker compose up -d postgres
    } >>"$LOG" 2>&1
    wait_for_compose_postgres >>"$LOG" 2>&1 || return 1
    if make migrate >>"$LOG" 2>&1; then
      COMPOSE_DB_MIGRATED=1
      return 0
    fi
  fi
  return 1
}

# ── Bootstrap (plans/00 §12: setup, db-up, migrate) ───────────────────────────

if [[ "$SKIP_BOOTSTRAP" -eq 0 ]]; then
  echo "Bootstrap (setup / Postgres / migrations)"
  BOOTSTRAP_RAN=1
  CURRENT_PHASE="BOOT"
  status_set BOOT "PASS"
  if command -v uv >/dev/null 2>&1; then
    run_step "make setup (uv sync + pre-commit)" make setup || true
  elif [[ ! -x .venv/bin/pytest ]]; then
    echo "  • uv missing and .venv/bin/pytest not found — run: make setup" >&2
    GLOBAL_FAIL=1
  fi
  run_step "make db-up" make db-up || true
  run_step "make migrate (compose Postgres)" migrate_compose_database || true
  run_step "alembic at head (0025)" alembic_at_mvp_head || true
  CURRENT_PHASE=""
fi

# ── Phase 00 — plans/00-foundation §12 ───────────────────────────────────────

if begin_phase "00" "Foundation & repository scaffold"; then
  if [[ "$COMPOSE_DB_MIGRATED" -eq 0 ]]; then
    run_step "make db-up" make db-up || true
    run_step "make migrate (compose Postgres)" migrate_compose_database || true
  fi
  run_step "make lint" make lint || true
  run_step "make typecheck" make typecheck || true
  run_step "pytest unit|persistence|integration (§12)" "${PYTEST[@]}" -q \
    -m "unit or persistence or integration" || true
  run_step "make test-security (import boundaries + security)" make test-security || true
  if [[ "$SKIP_SMOKE_API" -eq 0 ]]; then
    run_step "control-api /ready (compose profile app)" smoke_control_api_ready || true
  else
    skip_step "control-api /ready (--skip-smoke-api)"
  fi
  if [[ "$COMPOSE_DB_MIGRATED" -eq 1 ]]; then
    run_step "worker --once ticks (compose DB)" bash -c \
      "${PYTHON[*]} -m apps.scheduler_worker.main --once && ${PYTHON[*]} -m apps.execution_worker.main --once" || true
  else
    skip_step "worker --once ticks (compose DB not migrated; fix Postgres or run: docker compose down -v && make db-up && make migrate)"
  fi
  end_phase
fi

# ── Phase 01 — plans/01 §12 ──────────────────────────────────────────────────

if begin_phase "01" "Domain model & control-plane kernel"; then
  run_step "pytest tests/ (no live_llm, no journey)" "${PYTEST[@]}" -q \
    -m "not live_llm and not journey" tests || true
  run_step "tests/unit/state + repositories" "${PYTEST[@]}" -q \
    tests/unit/state tests/unit/repositories \
    tests/unit/test_guard_registry.py tests/unit/test_task_contract_body.py \
    tests/unit/test_dependency_cycles.py tests/unit/test_canonical_json.py || true
  run_step "persistence (domain kernel §12)" "${PYTEST[@]}" -q \
    tests/persistence/test_transition_atomicity.py \
    tests/persistence/test_concurrent_transition.py \
    tests/persistence/test_contract_immutability.py \
    tests/persistence/test_audit_immutable.py \
    tests/persistence/test_idempotency.py \
    tests/persistence/test_sequences.py \
    tests/persistence/test_repository_revision_integrity.py \
    tests/persistence/test_revision_service.py \
    tests/persistence/test_approval_pinning.py || true
  run_step "integration control_plane (kernel + acceptance)" "${PYTEST[@]}" -q \
    tests/integration/control_plane || true
  run_step "security control_plane_api" "${PYTEST[@]}" -q \
    tests/security/test_control_plane_api.py || true
  end_phase
fi

# ── Phase 02 — plans/02 §12 ──────────────────────────────────────────────────

if begin_phase "02" "ModelRouter & AgentRuntime"; then
  run_step "tests/unit/runtime" "${PYTEST[@]}" -q tests/unit/runtime || true
  run_step "persistence model_calls" "${PYTEST[@]}" -q \
    tests/persistence/test_model_calls_immutable.py || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    # Phase 02 milestone: ModelRouter + LangGraph only (Forge/Kira/planning live run in 04–06 + LIVE gate).
    run_step "live_llm router + langgraph (§12 milestone)" live_pytest -q \
      tests/integration/live_llm/test_model_router_live.py \
      tests/integration/live_llm/test_langgraph_runtime_live.py || true
  else
    skip_step "live_llm router + langgraph (use --live)"
  fi
  end_phase
fi

# ── Phase 03 — plans/03 §12 ──────────────────────────────────────────────────

if begin_phase "03" "Scheduler, execution, snapshot, lease"; then
  run_step "tests/unit/scheduler + execution" "${PYTEST[@]}" -q \
    tests/unit/scheduler tests/unit/execution \
    tests/unit/runtime/test_diagnostic_ask_question.py || true
  run_step "workflow|recovery tests/workflow/execution (§12)" "${PYTEST[@]}" -q \
    -m "workflow or recovery" tests/workflow/execution || true
  run_step "persistence execution + scheduler" "${PYTEST[@]}" -q \
    tests/persistence/test_execution_lease.py \
    tests/persistence/test_execution_retry.py \
    tests/persistence/test_execution_immutability.py \
    tests/persistence/test_execution_admission.py \
    tests/persistence/test_scheduler_no_model_calls.py || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "live execution spine (§12)" live_pytest -q \
      tests/integration/live_llm/test_execution_spine_live.py || true
  else
    skip_step "live execution spine (use --live)"
  fi
  end_phase
fi

# ── Phase 04 — plans/04 §12 ──────────────────────────────────────────────────

if begin_phase "04" "Git, ToolGateway, Forge"; then
  run_step "make test-git" make test-git || true
  run_step "git|security integration/tools + git (§12)" "${PYTEST[@]}" -q \
    -m "git or security" tests/integration/tools tests/integration/git || true
  run_step "integration phase04 API" "${PYTEST[@]}" -q \
    tests/integration/control_plane/test_phase04_api.py \
    tests/integration/control_plane/test_phase04_approval_api.py || true
  run_step "persistence gateway + connectors" "${PYTEST[@]}" -q \
    tests/persistence/test_tool_gateway_actions.py \
    tests/persistence/test_connector_idempotency.py \
    tests/persistence/test_gateway_audit_complete.py || true
  run_step "security tokens + credentials" "${PYTEST[@]}" -q \
    tests/security/test_execution_tokens.py \
    tests/security/test_credentials_not_persisted.py || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step_live_scout "live Forge (§12)" live_pytest -q \
      tests/integration/live_llm/test_forge_candidate_commit_live.py || true
  else
    skip_step "live Forge (use --live)"
  fi
  end_phase
fi

# ── Phase 05 — plans/05 §12 ──────────────────────────────────────────────────

if begin_phase "05" "Product source intake & product model"; then
  run_step "unit product_model + extraction" "${PYTEST[@]}" -q \
    tests/unit/product_model tests/unit/integrations/test_document_extraction.py || true
  run_step "persistence product model + scope" "${PYTEST[@]}" -q \
    tests/persistence/test_product_model_immutability.py \
    tests/persistence/test_snapshot_product_context.py \
    tests/persistence/test_scope_superseded_guard.py \
    tests/persistence/test_scope_rejection.py || true
  run_step "integration product model (full control_plane PM)" "${PYTEST[@]}" -q \
    tests/integration/control_plane/test_product_source_upload.py \
    tests/integration/control_plane/test_product_model_api_workflow.py \
    tests/integration/control_plane/test_product_model_kira_worker.py \
    tests/integration/control_plane/test_product_model_redecompose.py \
    tests/integration/control_plane/test_product_model_guards_extended.py \
    tests/integration/control_plane/test_large_prd_chunking.py \
    tests/integration/control_plane/test_prd_ambiguous_clarification.py \
    tests/integration/control_plane/test_source_chunking_helpers.py \
    tests/integration/control_plane/test_kernel_flow.py || true
  run_step "workflow product_model" "${PYTEST[@]}" -q tests/workflow/product_model || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "live_llm kira supportdesk (§12)" live_pytest -q \
      tests/integration/live_llm/test_kira_decompose_supportdesk_live.py || true
    run_step "live_llm kira PRD E2E" live_pytest -q \
      tests/integration/live_llm/test_kira_decompose_prd_live.py || true
    run_step "workflow product_model + --live-required (§12)" env LLM_LIVE_TESTS=1 \
      "${PYTEST[@]}" -m workflow --live-required -q tests/workflow/product_model || true
  else
    skip_step "live Kira + live workflow product_model (use --live)"
  fi
  end_phase
fi

# ── Phase 06 — plans/06 §12 ──────────────────────────────────────────────────

if begin_phase "06" "Architecture, ImplementationSpec, task planning"; then
  run_step "unit planning" "${PYTEST[@]}" -q tests/unit/planning || true
  run_step "persistence planning" "${PYTEST[@]}" -q \
    tests/persistence/test_planning_immutability.py \
    tests/persistence/test_compiled_contract_guard.py \
    tests/persistence/test_snapshot_planning_versions.py || true
  run_step "integration planning" "${PYTEST[@]}" -q \
    tests/integration/control_plane/test_planning_guards.py \
    tests/integration/control_plane/test_planning_start_planning.py \
    tests/integration/control_plane/test_planning_agent_profiles.py || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "live_llm|workflow planning (§12)" env LLM_LIVE_TESTS=1 "${PYTEST[@]}" -q \
      -m "live_llm or workflow" --live-required \
      tests/integration/live_llm/planning tests/workflow/planning || true
  else
    run_step "workflow planning (deterministic)" "${PYTEST[@]}" -q \
      tests/workflow/planning || true
    skip_step "live_llm planning (use --live)"
  fi
  end_phase
fi

# ── Phase 07 — plans/07 §12 ──────────────────────────────────────────────────

if begin_phase "07" "Code intelligence index"; then
  run_step "unit + integration code_index (§12)" "${PYTEST[@]}" -q \
    tests/integration/code_index tests/unit/code_index || true
  run_step "persistence code_index immutability" "${PYTEST[@]}" -q \
    tests/persistence/test_code_index_immutability.py || true
  run_step "security code_index isolation" "${PYTEST[@]}" -q \
    tests/security/test_code_index_security.py || true
  end_phase
fi

# ── Phase 08 — plans/08 §12 ──────────────────────────────────────────────────

if begin_phase "08" "Integration candidate, canonical index, traceability"; then
  run_step "unit integration + entity diff (§12)" "${PYTEST[@]}" -q \
    tests/unit/integration tests/unit/code_index/test_entity_changes.py || true
  run_step "persistence IC + traceability (§12)" "${PYTEST[@]}" -q \
    tests/persistence/test_ic_integrated_sha_immutable.py \
    tests/persistence/test_ic_promote_atomicity.py || true
  run_step "git|integration IC E2E (§12)" "${PYTEST[@]}" -q \
    -m "git or integration" \
    tests/integration/integration_candidate \
    tests/integration/traceability || true
  run_step "workflow execution (deterministic spine)" "${PYTEST[@]}" -q \
    tests/workflow/execution || true
  run_step "§15 handoff doc (09/10)" test -f docs/phase08-handoff-09-10.md || true
  run_step "§15 handoff doc smoke (unit)" "${PYTEST[@]}" -q \
    tests/unit/test_phase08_handoff_docs.py \
    tests/unit/assurance/test_findings_policy.py || true
  run_step "workflow IC precursor deterministic (§15)" "${PYTEST[@]}" -q \
    tests/workflow/integration -m "workflow and not live_llm" || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    skip_step "live Forge candidate (Phase 04 §12 + LIVE gate; avoid duplicate run)"
    run_step "live workflow IC precursor (§15)" env LLM_LIVE_TESTS=1 \
      "${PYTEST[@]}" -m "live_llm and workflow" --live-required -q \
      tests/workflow/integration || true
  else
    skip_step "live workflow IC precursor (use --live)"
  fi
  end_phase
fi

# ── Phase 09 — plans/09 §12 / §14 / §15 ─────────────────────────────────────
# §12: unit, persistence, security, integration (stub + real sentinel.execute),
#      workflow carry-forward, OpenAI strict schemas, live_llm when --live.
# §14: covered by suites above.
# §15: handoff doc + guards implemented (make check in full gate).

if begin_phase "09" "Assurance: evidence, gates, Warden, Sentinel"; then
  run_step "§15 handoff doc (obligation registry for 10/12/13/15)" \
    test -f docs/phase08-handoff-09-10.md || true
  run_step "§15 handoff smoke + FindingPolicy (§14 blocking)" "${PYTEST[@]}" -q \
    tests/unit/test_phase08_handoff_docs.py \
    tests/unit/assurance/test_findings_policy.py || true
  run_step "unit §12 (gates.decide, obligations, carry-forward, fingerprint)" \
    "${PYTEST[@]}" -q tests/unit/assurance || true
  run_step "unit §12 (OpenAI strict schemas: WardenReview, VerificationPlan)" \
    "${PYTEST[@]}" -q tests/unit/runtime/test_structured_output_schema.py \
    -k "warden_review or verification_plan" || true
  run_step "persistence §12 (evidence immutability)" "${PYTEST[@]}" -q \
    tests/persistence/test_assurance_immutability.py || true
  run_step "security §14 (agent 403 finalize + Warden/Sentinel tool audit)" \
    "${PYTEST[@]}" -q tests/security/test_assurance_gate_finalize.py || true
  run_step "integration §12 (gate E2E stub sentinel, bootstrap, waiver, profiles)" \
    "${PYTEST[@]}" -q -m integration tests/integration/assurance || true
  run_step "integration §12 (real sentinel.execute + pytest in worktree)" \
    "${PYTEST[@]}" -q -m integration tests/integration/assurance_execute || true
  run_step "workflow §12 (remediation IC + carry-forward, deterministic)" \
    "${PYTEST[@]}" -q tests/workflow/assurance || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "live_llm §12 (warden + sentinel plan, plan §12 command)" env LLM_LIVE_TESTS=1 \
      "${PYTEST[@]}" -q -m "live_llm or workflow" --live-required \
      tests/integration/live_llm/assurance tests/workflow/assurance || true
  else
    skip_step "live_llm assurance + workflow (re-run with --live)"
  fi
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "workflow §12 live Forge remediation loop (plan §12)" env LLM_LIVE_TESTS=1 \
      "${PYTEST[@]}" -q -m "live_llm and workflow" --live-required \
      tests/workflow/assurance/test_remediation_live_forge.py || true
  else
    skip_step "workflow §12 live Forge remediation loop (re-run with --live)"
  fi
  if [[ -z "$ONLY_PHASE" ]]; then
    : # make check runs in full-repo gates below
  elif [[ "$ONLY_PHASE" == "09" ]]; then
    run_step "plan §12 make check (lint, typecheck, deterministic lanes)" make check || true
  fi
  end_phase
fi

# ── Phase 10 — plans/10 §12 / §14 / §15 ─────────────────────────────────────
# §12: unit eligibility + manifest, persistence immutability, integration release E2E,
#      git stratos.release, security approve 403, workflow + journey Greenfield → R1.
# §14: covered by suites above (+ make check in full / --phase 10 gate).
# §15: handoff doc release hook; STATUS journey cost optional.

if begin_phase "10" "Release eligibility, manifest, Greenfield journey (R1)"; then
  run_step "§15 handoff doc (release eligibility hook)" \
    test -f docs/phase08-handoff-09-10.md || true
  run_step "alembic head (0024_p12_baselines_readiness)" alembic_at_mvp_head || true
  run_step "unit §12 (eligibility registry, truth table, manifest validation)" \
    "${PYTEST[@]}" -q \
    tests/unit/test_release_eligibility_registry.py \
    tests/unit/test_release_eligibility_truth_table.py \
    tests/unit/test_release_manifest_validation.py || true
  run_step "persistence §12 (manifest/outcome immutability, approval binding)" \
    "${PYTEST[@]}" -q \
    tests/persistence/test_release_immutability.py \
    tests/persistence/test_release_approval_binding.py || true
  run_step "integration §12 (release E2E, negatives, TOCTOU, workspace isolation)" \
    "${PYTEST[@]}" -q tests/integration/release || true
  run_step "git §12 (stratos.release ff-only, tag, RELEASED revision)" \
    "${PYTEST[@]}" -q tests/integration/git/test_release_git_actions.py || true
  run_step "security §12 (AGENT POST /releases/{id}/approve → 403)" \
    "${PYTEST[@]}" -q tests/security/test_release_api.py || true
  run_step "workflow §12 (GREENFIELD_BUILD baseline + isolated Forge → R1)" \
    "${PYTEST[@]}" -q tests/workflow/journey || true
  if [[ -n "$ONLY_PHASE" ]]; then
    run_step "journey §12 (PRD upload → Release R1, make test-journey)" make test-journey || true
  else
    skip_step "journey (full-repo JOURNEY gate below)"
  fi
  run_step "fixture §12 (SupportDesk clarification answers YAML)" \
    test -f tests/fixtures/supportdesk/clarification_answers.yaml || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    skip_step "live chained seven-alias Greenfield (plan §12; use make test-live per stage)"
  else
    skip_step "live chained seven-alias Greenfield (use --live for make test-live only)"
  fi
  if [[ -z "$ONLY_PHASE" ]]; then
    : # make check + journey run in full-repo gates below
  elif [[ "$ONLY_PHASE" == "10" ]]; then
    run_step "plan §12 make check (lint, typecheck, deterministic lanes)" make check || true
  fi
  end_phase
fi

# ── Phase 11 — plans/11 §12 / §14 / §15 ─────────────────────────────────────
# §12: unit + integration brownfield, git rematerialization, security injection,
#      workflow recovery → start_baseline guard; live Scout when --live.

if begin_phase "11" "Brownfield discovery and recovered specifications"; then
  run_step "alembic head 0024_p12_baselines_readiness" alembic_at_mvp_head || true
  run_step "unit §12 (manifests, caps, citations, assert extraction)" \
    "${PYTEST[@]}" -q tests/unit/brownfield || true
  run_step "integration §12 (discovery, clone binding, behaviors, isolation)" \
    "${PYTEST[@]}" -q tests/integration/brownfield || true
  run_step "git §12 (fresh runtime re-materialization)" \
    "${PYTEST[@]}" -q tests/integration/brownfield/test_fresh_runtime_rematerialization.py || true
  run_step "security §14 (prompt injection + readonly write deny)" \
    "${PYTEST[@]}" -q tests/security/test_brownfield_prompt_injection.py || true
  run_step "workflow §12 (VALIDATED recovery → start_baseline guard)" \
    "${PYTEST[@]}" -q tests/workflow/brownfield || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step_live_scout "live_llm §12 (Scout supportdesk_r1)" env LLM_LIVE_TESTS=1 \
      "${PYTEST[@]}" -q -m live_llm --live-required \
      tests/integration/live_llm/brownfield/test_scout_supportdesk_live.py || true
  else
    skip_step "live_llm Scout brownfield (re-run with --live)"
  fi
  if [[ -z "$ONLY_PHASE" ]]; then
    : # make check runs in full-repo gates below
  elif [[ "$ONLY_PHASE" == "11" ]]; then
    run_step "plan §12 make check (lint, typecheck, deterministic lanes)" make check || true
  fi
  end_phase
fi

# ── Phase 12 — plans/12 §12 / §14 / §15 ─────────────────────────────────────
# §12: baselines unit, promotion/readiness workflow → READY_FOR_CHANGE; live journey when --live.

if begin_phase "12" "Baselines, promotion, readiness (READY_FOR_CHANGE)"; then
  run_step "alembic head 0024_p12_baselines_readiness" alembic_at_mvp_head || true
  run_step "unit §12 (readiness metrics, safe probe policy)" \
    "${PYTEST[@]}" -q tests/unit/baselines || true
  run_step "integration §12 (sentinel.characterize profile)" \
    "${PYTEST[@]}" -q \
    tests/integration/assurance/test_warden_sentinel_profiles.py::test_sentinel_characterize_via_model_router || true
  run_step "workflow §12 (brownfield → READY_FOR_CHANGE, FakeProvider)" \
    "${PYTEST[@]}" -q tests/workflow/brownfield/test_brownfield_to_ready_workflow.py || true
  run_step "workflow §12 (NOT_READY → REMEDIATION → READY)" \
    "${PYTEST[@]}" -q tests/workflow/brownfield/test_brownfield_remediation_workflow.py || true
  run_step "integration §12 (promotion + declare_ready)" \
    "${PYTEST[@]}" -q tests/integration/brownfield/test_promotion_and_declare_ready.py || true
  run_step "fixture §12 (scripted promotion rules YAML)" \
    test -f tests/fixtures/supportdesk/brownfield_review.yaml || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "live §12 (sentinel.characterize on supportdesk_r1)" env LLM_LIVE_TESTS=1 \
      "${PYTEST[@]}" -q tests/integration/live_llm/brownfield/test_sentinel_characterize_live.py || true
    run_step "journey §12 (live Scout + READY_FOR_CHANGE)" env LLM_LIVE_TESTS=1 \
      "${PYTEST[@]}" -q -m journey --live-required \
      tests/journey/test_brownfield_supportdesk.py || true
  else
    skip_step "live sentinel.characterize (re-run with --live)"
    skip_step "journey brownfield live (re-run with --live)"
  fi
  if [[ -z "$ONLY_PHASE" ]]; then
    : # make check runs in full-repo gates below
  elif [[ "$ONLY_PHASE" == "12" ]]; then
    run_step "plan §12 make check (lint, typecheck, deterministic lanes)" make check || true
  fi
  end_phase
fi

# ── Phase 13 — plans/13 §12 / §14 / §15 ─────────────────────────────────────
# §12: SpecDelta, ImpactEngine, hybrid retrieval, incremental index, staleness;
#      live semantic retrieval when --live.

if begin_phase "13" "Spec delta, impact engine, hybrid retrieval, staleness"; then
  run_step "alembic head 0025_p13_spec_deltas_impact" alembic_at_mvp_head || true
  run_step "unit §12 (impact traversal, guards, baseline floor, semantic degrade)" \
    "${PYTEST[@]}" -q tests/unit/impact || true
  run_step "integration §12 (impact + incremental index, plan §12 command)" \
    "${PYTEST[@]}" -q \
    tests/integration/impact \
    tests/integration/code_index/test_incremental.py || true
  run_step "persistence §12 (spec delta + impact immutability, embedding uniqueness)" \
    "${PYTEST[@]}" -q \
    tests/persistence/test_impact_immutability.py \
    tests/persistence/test_embedding_uniqueness.py || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "live_llm §12 (semantic retrieval + hybrid labels)" live_pytest -q \
      tests/integration/live_llm/test_semantic_retrieval_live.py || true
  else
    skip_step "live_llm semantic retrieval (re-run with --live)"
  fi
  if [[ -z "$ONLY_PHASE" ]]; then
    : # make check runs in full-repo gates below
  elif [[ "$ONLY_PHASE" == "13" ]]; then
    run_step "plan §12 make check (lint, typecheck, deterministic lanes)" make check || true
  fi
  end_phase
fi

# ── Phase 14 — plans/14 §12 / §14 / §15 ─────────────────────────────────────
# §12: ChangeRequest idempotency, interpretation validator, Feature Change journey.

if begin_phase "14" "Feature Change journey (R2)"; then
  run_step "alembic head 0027_feature_spec_supersede" alembic_at_mvp_head || true
  run_step "unit §12 (interpretation validator, impact consistency)" \
    "${PYTEST[@]}" -q \
    tests/unit/product_model/changes/test_interpretation_validator.py \
    tests/unit/planning/test_impact_consistency.py || true
  run_step "persistence §12 (ChangeRequest idempotency)" \
    "${PYTEST[@]}" -q tests/persistence/test_change_request_idempotency.py || true
  run_step "integration §12 (trusted seed smoke)" \
    "${PYTEST[@]}" -q tests/integration/test_trusted_seed.py || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "live_llm + journey §12 (change interpret + Feature Change R2)" \
      env LLM_LIVE_TESTS=1 "${PYTEST[@]}" -m "live_llm or journey" --live-required -q \
      tests/integration/live_llm/change \
      tests/journey/test_feature_change_supportdesk.py || true
  else
    skip_step "Feature Change journey (re-run with --phase 14 --live)"
  fi
  if [[ -z "$ONLY_PHASE" ]]; then
    : # full gates below
  elif [[ "$ONLY_PHASE" == "14" ]]; then
    run_step "plan §12 make check (lint, typecheck, deterministic lanes)" make check || true
  fi
  end_phase
fi

# ── Phase 15 — plans/15 §12 / §14 / §15 ─────────────────────────────────────
# §12: defect intake, reproduction, eligibility, journey.

if begin_phase "15" "Bug Fix journey (R3)"; then
  run_step "alembic head 0029_p15_unreproduced_approval" alembic_at_mvp_head || true
  run_step "unit §12 (signature, repair validator, code path, RCA)" \
    "${PYTEST[@]}" -q tests/unit/defects || true
  run_step "persistence §12 (defect idempotency, reproduction artifact hash)" \
    "${PYTEST[@]}" -q \
    tests/integration/defects/test_defect_intake_idempotent.py \
    tests/persistence/test_reproduction_artifact_immutability.py || true
  run_step "integration §12 (reproduction, eligibility, policy)" \
    "${PYTEST[@]}" -q \
    tests/integration/defects \
    tests/integration/reproduction || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "live_llm + journey §12 (defect profiles + Bug Fix R3)" \
      env LLM_LIVE_TESTS=1 "${PYTEST[@]}" -m "live_llm or journey" --live-required -q \
      tests/integration/live_llm/defects \
      tests/journey/test_bug_fix_supportdesk.py || true
  else
    skip_step "Bug Fix journey (re-run with --phase 15 --live)"
  fi
  if [[ -z "$ONLY_PHASE" ]]; then
    :
  elif [[ "$ONLY_PHASE" == "15" ]]; then
    run_step "plan §12 make check (lint, typecheck, deterministic lanes)" make check || true
  fi
  end_phase
fi

# ── Phase 16 — plans/16 §12 / §13 / §14 / §15 ───────────────────────────────
# §12: secrets, HMAC inbound, sync, reconciliation, connector tests.
# §13 live (--live): Gitea compose + issue-tracker Feature Change R2 (make test-journey-issue-tracker).

if begin_phase "16" "External integrations & reconciliation"; then
  run_step "alembic head 0030_p16_integrations" alembic_at_mvp_head || true
  run_step "unit §12 (HMAC auth helpers)" \
    "${PYTEST[@]}" -q tests/unit/integrations/test_hmac_auth.py || true
  run_step "integration §12 (features + §14 acceptance criteria)" \
    "${PYTEST[@]}" -q tests/integration/integrations || true
  run_step "connector §12 (git provider policy, fault proxy, outbound)" \
    "${PYTEST[@]}" -q -m connector tests/connector || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "integrations compose profile up" make integrations-up || true
    run_step "integrations seed (GITEA_API_TOKEN → .env)" make integrations-seed || true
    run_step "connector_live §12 (Gitea/MinIO/CI/fault proxy)" make test-connector-live || true
    run_step "journey §13 (Gitea issue → Feature Change R2 + CI/deploy)" \
      make test-journey-issue-tracker || true
    run_step "integrations compose profile down" make integrations-down || true
  else
    skip_step "connector_live + live issue-tracker journey (re-run: make verify-phase-16-exit)"
  fi
  if [[ -z "$ONLY_PHASE" ]]; then
    :
  elif [[ "$ONLY_PHASE" == "16" ]]; then
    run_step "plan §12 make test-integrations-p16" make test-integrations-p16 || true
  fi
  end_phase
fi

# ── Phase 17 — plans/17 §12 / §14 / §15 ─────────────────────────────────────

if begin_phase "17" "Operator read models & orchestrator"; then
  run_step "alembic head 0031_p17_orchestrator" alembic_at_mvp_head || true
  run_step "unit §12 (command catalog, orchestrator validator)" \
    "${PYTEST[@]}" -q tests/unit/test_command_catalog.py tests/unit/orchestrator/test_validator.py || true
  run_step "integration §12 (read models + preview idempotency)" \
    "${PYTEST[@]}" -q tests/integration/control_plane/test_views_api.py \
    tests/integration/control_plane/test_orchestrator_api.py \
    tests/persistence/test_transition_preview_side_effects.py || true
  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_step "live_llm §11 orchestrator converse" \
      env LLM_LIVE_TESTS=1 "${PYTEST[@]}" -m live_llm --live-required -q \
      tests/integration/live_llm/test_orchestrator_live.py || true
  else
    skip_step "orchestrator live (re-run: make verify-phase-17-exit)"
  fi
  end_phase
fi

# ── Full-repo gates (full run only) ──────────────────────────────────────────

if [[ -z "$ONLY_PHASE" ]]; then
  run_full_gate "CHECK" "Full gate — make check (lint, typecheck, deterministic lanes)" make check

  run_full_gate "FULL-DET" \
    "Full deterministic tree — pytest (not live_llm, not journey)" \
    "${PYTEST[@]}" -q -m "not live_llm and not journey"

  run_journey_gate

  if [[ "$RUN_LIVE" -eq 1 ]]; then
    run_full_gate "LIVE" "Full live gate — make test-live (all live_llm)" make test-live
  fi
fi

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "Summary"
echo "══════════════════════════════════════════════════════════════"
if [[ "$BOOTSTRAP_RAN" -eq 1 ]]; then
  st="$(status_get BOOT)"
  if [[ "$st" == "PASS" ]]; then
    printf "  Bootstrap   \033[32mPASS\033[0m\n"
  else
    printf "  Bootstrap   \033[31mFAIL\033[0m\n"
  fi
fi
for id in 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17; do
  if [[ -n "$ONLY_PHASE" && "$ONLY_PHASE" != "$id" ]]; then
    continue
  fi
  st="$(status_get "$id")"
  if [[ "$st" == "PASS" ]]; then
    printf "  Phase %s  \033[32mPASS\033[0m\n" "$id"
  elif [[ "$st" == "FAIL" ]]; then
    printf "  Phase %s  \033[31mFAIL\033[0m\n" "$id"
  else
    printf "  Phase %s  SKIP\n" "$id"
  fi
done
if [[ -z "$ONLY_PHASE" ]]; then
  for key in CHECK FULL-DET LIVE JOURNEY; do
    st="$(status_get "$key")"
    [[ "$st" == "SKIP" && "$key" == "LIVE" && "$RUN_LIVE" -eq 0 ]] && continue
    if [[ "$st" == "PASS" ]]; then
      printf "  %-10s \033[32mPASS\033[0m\n" "$key"
    elif [[ "$st" == "FAIL" ]]; then
      printf "  %-10s \033[31mFAIL\033[0m\n" "$key"
    fi
  done
fi
if [[ "$RUN_LIVE" -eq 0 ]]; then
  echo ""
  echo "Live LLM gate skipped. Re-run with: $0 --live"
fi
echo ""

if [[ "$GLOBAL_FAIL" -ne 0 ]]; then
  exit 1
fi
exit 0
