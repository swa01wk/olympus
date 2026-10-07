# Dashboard test fixtures

JSON fixtures for Playwright route mocking. No secrets — use fake UUIDs only.

Run e2e (requires dev server):

```bash
cd apps/dashboard
npm run test:e2e
```

Set `NEXT_PUBLIC_OLYMPUS_API_URL` to match the app; tests stub `/projects` and `/actors/me`.
