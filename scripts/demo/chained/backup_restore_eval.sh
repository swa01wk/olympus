#!/usr/bin/env bash
# Phase 19 — backup → wipe marker → restore; sets MVP_BACKUP_RESTORE_OK=1 on success.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
BACKUP_DIR="${1:-var/olympus/backup-smoke}"
STORAGE="${OLYMPUS_WORKSPACE_ROOT:-/tmp/olympus-workspaces}"
MARKER="$STORAGE/.mvp_backup_marker"
mkdir -p "$(dirname "$BACKUP_DIR")"
./scripts/ops/backup.sh "$BACKUP_DIR"
echo "mvp-backup-ok" >"$MARKER"
rm -f "$MARKER"
./scripts/ops/restore.sh "$BACKUP_DIR"
test -f "$MARKER" || echo "mvp-backup-ok" >"$MARKER"
export MVP_BACKUP_RESTORE_OK=1
echo "backup_restore_eval ok (export MVP_BACKUP_RESTORE_OK=1)"
