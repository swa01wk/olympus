# Restart runbook

1. Stop workers: execution-worker, scheduler-worker (SIGTERM; wait one poll interval).
2. Restart control-api; confirm `GET /ready` returns 200 (db, migrations, storage, sandbox).
3. Start scheduler-worker, then execution-worker.
4. Verify `GET /audit/verify?project_id=<uuid>` for active projects.
5. If cycles were mid-flight, check `GET /ops/invariants?project_id=<uuid>`.
