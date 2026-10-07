#!/usr/bin/env bash
set -euo pipefail
SRC="${1:?usage: restore.sh /path/to/backup-dir}"
: "${DATABASE_URL:?DATABASE_URL required}"
: "${OLYMPUS_STORAGE_ROOT:?OLYMPUS_STORAGE_ROOT required}"
: "${OLYMPUS_WORKSPACE_ROOT:?OLYMPUS_WORKSPACE_ROOT required}"

pg_restore --clean --if-exists --dbname="$DATABASE_URL" "$SRC/olympus.dump"
rm -rf "$OLYMPUS_STORAGE_ROOT" "$OLYMPUS_WORKSPACE_ROOT"
mkdir -p "$(dirname "$OLYMPUS_STORAGE_ROOT")" "$(dirname "$OLYMPUS_WORKSPACE_ROOT")"
tar -xzf "$SRC/storage.tgz" -C "$(dirname "$OLYMPUS_STORAGE_ROOT")"
tar -xzf "$SRC/workspaces.tgz" -C "$(dirname "$OLYMPUS_WORKSPACE_ROOT")"
echo "restore complete from $SRC"
