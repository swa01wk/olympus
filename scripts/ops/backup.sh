#!/usr/bin/env bash
set -euo pipefail
DEST="${1:?usage: backup.sh /path/to/backup-dir}"
mkdir -p "$DEST"
: "${DATABASE_URL:?DATABASE_URL required}"
: "${OLYMPUS_STORAGE_ROOT:?OLYMPUS_STORAGE_ROOT required}"
: "${OLYMPUS_WORKSPACE_ROOT:?OLYMPUS_WORKSPACE_ROOT required}"

pg_dump "$DATABASE_URL" --format=custom --file="$DEST/olympus.dump"
tar -czf "$DEST/storage.tgz" -C "$(dirname "$OLYMPUS_STORAGE_ROOT")" "$(basename "$OLYMPUS_STORAGE_ROOT")"
tar -czf "$DEST/workspaces.tgz" -C "$(dirname "$OLYMPUS_WORKSPACE_ROOT")" "$(basename "$OLYMPUS_WORKSPACE_ROOT")"
echo "backup complete: $DEST"
