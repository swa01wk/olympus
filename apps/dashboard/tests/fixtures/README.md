# Dashboard test fixtures

JSON fixtures for Playwright route mocking. No secrets — use fake UUIDs only.

Run e2e (requires dev server):

```bash
cd apps/dashboard
npm run test:e2e
```

Set `NEXT_PUBLIC_OLYMPUS_API_URL` to match the app; tests stub `/projects` and `/actors/me`.

### Live studio (`@live`)

`tests/e2e/studio-greenfield.spec.ts` hits a real Control API and is **skipped** when the API or tokens are missing.

```bash
# Terminal 1: make db-up && make migrate && uvicorn … + workers
# Terminal 2:
cd apps/dashboard
export NEXT_PUBLIC_OLYMPUS_API_URL=http://127.0.0.1:8000
export OLYMPUS_OPERATOR_TOKEN="$(uv run python -m apps.control_api.cli.seed_actor --name studio-op --roles OPERATOR)"
export OLYMPUS_APPROVER_TOKEN="$(uv run python -m apps.control_api.cli.seed_actor --name studio-ap --roles OPERATOR,APPROVER)"
npm run test:e2e:live
```
