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
# Recommended (Docker API + workers with LocalSandbox — see deploy/compose.studio-live.yaml):
./scripts/demo/studio-live-smoke.sh
# Or RL2 only:
./scripts/demo/studio-live-smoke.sh tests/e2e/studio-rl2.spec.ts

# Manual:
# docker compose -f docker-compose.yml -f deploy/compose.demo.yaml \
#   -f deploy/compose.studio-live.yaml --profile demo up -d postgres control-api scheduler-worker execution-worker
# make migrate && … npm run test:e2e:live
```
