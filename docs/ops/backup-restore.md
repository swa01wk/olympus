# Backup and restore

## Backup

```bash
export DATABASE_URL=postgresql://olympus:olympus@localhost:5432/olympus
export OLYMPUS_STORAGE_ROOT=./var/olympus
export OLYMPUS_WORKSPACE_ROOT=./var/olympus/workspaces
scripts/ops/backup.sh /tmp/olympus-backup
```

Creates `olympus.dump`, `storage.tgz`, and `workspaces.tgz` (no credential values in the tarball paths).

## Restore

```bash
scripts/ops/restore.sh /tmp/olympus-backup
```

Then restart all processes and run `/ready` plus audit chain verification.
