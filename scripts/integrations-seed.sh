#!/usr/bin/env bash
# Bootstrap OSS integration stack credentials (Gitea API token).
# Run after: make integrations-up
#
# Usage:
#   export GITEA_API_TOKEN="$(./scripts/integrations-seed.sh)"
#   # optional: append to .env
#   ./scripts/integrations-seed.sh --write-env
#
# Prints only the token on stdout (stderr has progress).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WRITE_ENV=0
if [[ "${1:-}" == "--write-env" ]]; then
  WRITE_ENV=1
fi

GITEA_URL="${OLYMPUS_GITEA_URL:-http://127.0.0.1:3000}"
GITEA_URL="${GITEA_URL%/}"
USER="${GITEA_ADMIN_USER:-olympus}"
PASS="${GITEA_ADMIN_PASSWORD:-olympus-integration}"
EMAIL="${GITEA_ADMIN_EMAIL:-olympus@test.local}"
TOKEN_NAME="${GITEA_TOKEN_NAME:-olympus-integration-test}"

COMPOSE=(docker compose -f docker-compose.yml -f deploy/compose.test.yaml)

log() { echo "$*" >&2; }

wait_gitea() {
  local i
  for i in $(seq 1 60); do
    if curl -sf "${GITEA_URL}/api/v1/version" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  log "Gitea not reachable at ${GITEA_URL} (run: make integrations-up)"
  return 1
}

ensure_admin_user() {
  if curl -sf -u "${USER}:${PASS}" "${GITEA_URL}/api/v1/user" >/dev/null 2>&1; then
    log "Gitea admin user '${USER}' already exists"
    return 0
  fi
  log "Creating Gitea admin user '${USER}' via container CLI..."
  "${COMPOSE[@]}" exec -T gitea gitea admin user create \
    --username "${USER}" \
    --password "${PASS}" \
    --email "${EMAIL}" \
    --admin \
    --must-change-password=false 2>/dev/null || true
  if ! curl -sf -u "${USER}:${PASS}" "${GITEA_URL}/api/v1/user" >/dev/null 2>&1; then
    log "Could not authenticate as ${USER}. Complete Gitea install at ${GITEA_URL} manually."
    return 1
  fi
}

delete_existing_token() {
  local list id
  list="$(curl -sf -u "${USER}:${PASS}" "${GITEA_URL}/api/v1/users/${USER}/tokens" 2>/dev/null || true)"
  if [[ -z "$list" ]]; then
    return 0
  fi
  id="$(python3 -c "
import json, sys
name = sys.argv[1]
for t in json.load(sys.stdin):
    if t.get('name') == name and t.get('id') is not None:
        print(t['id'])
        break
" "$TOKEN_NAME" <<<"$list")"
  if [[ -n "$id" ]]; then
    log "Replacing existing Gitea API token '${TOKEN_NAME}' (id ${id})..."
    curl -sf -u "${USER}:${PASS}" -X DELETE "${GITEA_URL}/api/v1/users/${USER}/tokens/${id}" >/dev/null 2>&1 || true
  fi
}

create_api_token() {
  local resp
  delete_existing_token
  resp="$(curl -sf -u "${USER}:${PASS}" \
    -H "Content-Type: application/json" \
    -X POST "${GITEA_URL}/api/v1/users/${USER}/tokens" \
    -d "{\"name\":\"${TOKEN_NAME}\",\"scopes\":[\"all\"]}" 2>/dev/null || true)"
  if [[ -z "$resp" ]]; then
    log "Token create failed for '${TOKEN_NAME}' (is Gitea up? curl ${GITEA_URL}/api/v1/version)"
    return 1
  fi
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('sha1') or d.get('token') or '')" <<<"$resp"
}

wait_gitea
ensure_admin_user
TOKEN="$(create_api_token)"
if [[ -z "${TOKEN:-}" ]]; then
  exit 1
fi

log "Gitea API token created (name: ${TOKEN_NAME})"
log "Export: export GITEA_API_TOKEN=..."

if [[ "$WRITE_ENV" -eq 1 ]]; then
  ENV_FILE="${ROOT}/.env"
  touch "$ENV_FILE"
  if grep -q '^GITEA_API_TOKEN=' "$ENV_FILE" 2>/dev/null; then
    sed -i.bak "s|^GITEA_API_TOKEN=.*|GITEA_API_TOKEN=${TOKEN}|" "$ENV_FILE"
    rm -f "${ENV_FILE}.bak"
  else
    printf '\nGITEA_API_TOKEN=%s\n' "$TOKEN" >>"$ENV_FILE"
  fi
  log "Updated GITEA_API_TOKEN in .env"
  exit 0
fi

printf '%s' "$TOKEN"
